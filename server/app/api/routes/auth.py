from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import CurrentUserDep, SessionDep
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.email_verification_code import (
    EmailVerificationCode,
    EmailVerificationPurpose,
)
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SendVerificationCodeRequest,
    TokenResponse,
    UserResponse,
)
from app.services.email_sender import send_email
from app.services.email_verification import (
    build_verification_email,
    generate_verification_code,
    get_verification_expiry,
    hash_verification_code,
)

router = APIRouter()


"""
    发送注册验证码接口。
    
    1. 校验邮箱是否已被注册。
    2. 校验发送频率（冷却时间）。
    3. 生成随机验证码并发送邮件。
    4. 将哈希后的验证码及过期时间存入数据库。
"""
@router.post(
    "/send-verification-code",
    summary="发送注册邮箱验证码",
    description="向指定邮箱发送注册验证码，用于注册前校验邮箱归属。",
)
def send_verification_code(
    payload: SendVerificationCodeRequest,
    session: SessionDep,
) -> dict[str, str]:
    
    email = payload.email.lower()
    
    # 1. 检查邮箱是否已存在
    existing_user = session.exec(select(User).where(User.email == email)).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已经注册",
        )

    # 2. 频率控制校验（检查近期是否已发过验证码）
    now = datetime.now(timezone.utc)
    cooldown_started_at = now - timedelta(
        seconds=settings.email_verification_code_cooldown_seconds
    )
    recent_code = session.exec(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == EmailVerificationPurpose.REGISTER,
            EmailVerificationCode.consumed_at.is_(None),
            EmailVerificationCode.created_at >= cooldown_started_at,
        )
        .order_by(EmailVerificationCode.created_at.desc())
    ).first()
    if recent_code is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码发送过于频繁，请稍后再试",
        )

    # 3. 生成并发送验证码邮件
    code = generate_verification_code()
    subject, body_text = build_verification_email(code)
    result = send_email(email, subject, body_text)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"验证码邮件发送失败：{result.error_message}",
        )

    # 4. 数据库中保存验证码记录
    verification_code = EmailVerificationCode(
        email=email,
        purpose=EmailVerificationPurpose.REGISTER,
        code_hash=hash_verification_code(
            email=email,
            purpose=EmailVerificationPurpose.REGISTER,
            code=code,
        ),
        expires_at=get_verification_expiry(),
    )
    session.add(verification_code)
    session.commit()
    return {"message": "验证码已发送"}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册用户",
    description="使用邮箱和密码注册新用户。邮箱作为用户名，必须唯一。",
)
def register(payload: RegisterRequest, session: SessionDep) -> User:
    """
    新用户注册接口。
    
    1. 校验邮箱是否已被注册。
    2. 如果系统配置要求验证码：
       a. 获取最新未消费且未过期的验证码记录。
       b. 校验错误尝试次数是否超限。
       c. 校验验证码正确性，若错误则增加错误计数。
       d. 校验成功后将验证码标记为已使用（consumed_at）。
    3. 创建用户，对密码进行哈希处理并持久化到数据库。
    """
    email = payload.email.lower()
    
    # 1. 检查邮箱是否已存在
    existing_user = session.exec(select(User).where(User.email == email)).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已经注册",
        )

    # 2. 邮箱验证码校验逻辑（如果系统配置中开启了邮箱注册验证）
    if settings.registration_email_verification_required:
        if payload.verification_code is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="请先获取并填写邮箱验证码",
            )

        now = datetime.now(timezone.utc)
        
        # 查找当前最新、未被使用过且未过期的注册验证码记录
        verification_code = session.exec(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == EmailVerificationPurpose.REGISTER,
                EmailVerificationCode.consumed_at.is_(None),
                EmailVerificationCode.expires_at > now,
            )
            .order_by(EmailVerificationCode.created_at.desc())
        ).first()
        if verification_code is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码无效或已过期",
            )

        # 校验尝试次数上限
        if verification_code.attempts >= settings.email_verification_max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误次数过多，请重新获取",
            )

        # 校验验证码哈希值
        expected_hash = hash_verification_code(
            email=email,
            purpose=EmailVerificationPurpose.REGISTER,
            code=payload.verification_code,
        )
        if verification_code.code_hash != expected_hash:
            verification_code.attempts += 1
            verification_code.updated_at = now
            session.add(verification_code)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误",
            )

        # 验证通过，标记该验证码为已使用状态
        verification_code.consumed_at = now
        verification_code.updated_at = now
        session.add(verification_code)

    # 3. 创建并保存新用户
    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="使用邮箱和密码登录，登录成功后返回 JWT access_token。",
)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    """
    用户登录认证接口。
    
    1. 查找用户并验证密码哈希。
    2. 校验用户账号是否处于活跃状态。
    3. 签发 JWT Access Token 并返回。
    """
    email = payload.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    
    # 1. 验证用户存在性与密码正确性
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )
        
    # 2. 检查用户账号是否启用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该用户已被禁用",
        )

    # 3. 签发并返回 JWT 访问令牌
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户",
    description="根据请求头中的 Bearer Token 获取当前登录用户信息。",
)
def get_me(current_user: CurrentUserDep) -> User:
    """
    获取当前登录用户信息接口。
    
    通过依赖注入 CurrentUserDep 解析请求头中 Bearer 携带的 JWT 令牌，
    校验成功后直接返回当前用户的详细数据。
    """
    return current_user


@router.post(
    "/change-password",
    summary="修改当前用户密码",
    description="当前登录用户通过旧密码验证后修改新密码。",
)
def change_password(
    payload: ChangePasswordRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict[str, str]:
    """
    用户自主修改密码接口。
    
    1. 校验提交的旧密码是否正确。
    2. 限制新旧密码不能相同。
    3. 生成新密码哈希并持久化保存。
    """
    # 1. 验证旧密码是否匹配
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="旧密码错误",
        )

    # 2. 验证新旧密码是否相同
    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能和旧密码相同",
        )

    # 3. 哈希新密码并更新保存
    current_user.password_hash = hash_password(payload.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    session.add(current_user)
    session.commit()
    return {"message": "密码已修改"}


@router.post(
    "/logout",
    summary="退出登录",
    description="服务端不保存登录会话，前端删除本地 token 即可完成退出。",
)
def logout() -> dict[str, str]:
    """
    退出登录接口（占位）。
    
    采用无状态的 JWT 认证方案，注销操作在前端清除 Token 即可完成。
    此接口仅供客户端以标准流程调用并作为成功返回响应。
    """
    return {"message": "已退出登录"}
