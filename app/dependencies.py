from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    # Depends(callable or your_function) is a FastAPI dependency injection design pattern
    # pre-processor that runs before your function and injects the result into the parameter.
    # Resolves any requirements that function might have (including its own dependencies).
    # Passes the result directly into your route as a parameter.
    # This is similar to Java/Spring's @Autowired dependency injection 
    # and @AuthenticationPrincipal for filter-based extraction for security credentials.
    # Pros:
    # 1. Code Reuse: Shared logic like pagination or API keys is defined once and used across multiple endpoints.
    # 2. Automatic Caching: If multiple dependencies in the same request need the same "sub-dependency," FastAPI calls it once and reuses the result.
    # 3. Sub-dependencies: Dependencies can depend on other dependencies, creating a clean "tree" of logic.
    # 4. Testing: You can easily swap real dependencies (like a production database) with "mocks" during testing using app.dependency_overrides
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
