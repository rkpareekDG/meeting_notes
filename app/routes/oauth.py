"""OAuth callback routes for handling OAuth redirects."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse

from app.services.oauth import oauth_service
from app.repositories.oauth import oauth_repository
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/oauth", tags=["oauth"])


# Success/Error HTML templates
SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Successful</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            text-align: center;
            background: white;
            padding: 40px 60px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #1a1a2e; margin-bottom: 10px; }}
        p {{ color: #666; margin-bottom: 20px; }}
        .provider {{ 
            display: inline-block;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border-radius: 20px;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">✅</div>
        <h1>Authorization Successful!</h1>
        <p>You have successfully connected <span class="provider">{provider}</span></p>
        <p>You can close this window and return to Slack.</p>
    </div>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Failed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        }}
        .container {{
            text-align: center;
            background: white;
            padding: 40px 60px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #1a1a2e; margin-bottom: 10px; }}
        p {{ color: #666; }}
        .error {{ color: #eb3349; font-size: 14px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">❌</div>
        <h1>Authorization Failed</h1>
        <p>Something went wrong during the authorization process.</p>
        <p class="error">{error}</p>
        <p>Please return to Slack and try again.</p>
    </div>
</body>
</html>
"""


@router.get("/zoom/callback", response_class=HTMLResponse)
async def zoom_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Handle Zoom OAuth callback.
    
    Args:
        code: Authorization code
        state: State for CSRF validation
        error: Error if authorization failed
        
    Returns:
        HTML response
    """
    if error:
        logger.error("Zoom OAuth error", error=error)
        return HTMLResponse(ERROR_HTML.format(error=error), status_code=400)
    
    if not code or not state:
        return HTMLResponse(
            ERROR_HTML.format(error="Missing code or state"),
            status_code=400,
        )
    
    token = await oauth_service.exchange_zoom_code(code, state)
    
    if not token:
        return HTMLResponse(
            ERROR_HTML.format(error="Failed to exchange authorization code"),
            status_code=400,
        )
    
    logger.info("Zoom OAuth successful", user_id=token.user_id)
    return HTMLResponse(SUCCESS_HTML.format(provider="Zoom"))


@router.get("/microsoft/callback", response_class=HTMLResponse)
async def microsoft_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    """Handle Microsoft OAuth callback.
    
    Args:
        code: Authorization code
        state: State for CSRF validation
        error: Error code
        error_description: Error description
        
    Returns:
        HTML response
    """
    if error:
        logger.error("Microsoft OAuth error", error=error, description=error_description)
        return HTMLResponse(
            ERROR_HTML.format(error=error_description or error),
            status_code=400,
        )
    
    if not code or not state:
        return HTMLResponse(
            ERROR_HTML.format(error="Missing code or state"),
            status_code=400,
        )
    
    token = await oauth_service.exchange_microsoft_code(code, state)
    
    if not token:
        return HTMLResponse(
            ERROR_HTML.format(error="Failed to exchange authorization code"),
            status_code=400,
        )
    
    logger.info("Microsoft OAuth successful", user_id=token.user_id)
    return HTMLResponse(SUCCESS_HTML.format(provider="Microsoft 365"))


@router.get("/jira/callback", response_class=HTMLResponse)
async def jira_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    """Handle Jira/Atlassian OAuth callback.
    
    Args:
        code: Authorization code
        state: State for CSRF validation
        error: Error code
        error_description: Error description
        
    Returns:
        HTML response
    """
    if error:
        logger.error("Jira OAuth error", error=error, description=error_description)
        return HTMLResponse(
            ERROR_HTML.format(error=error_description or error),
            status_code=400,
        )
    
    if not code or not state:
        return HTMLResponse(
            ERROR_HTML.format(error="Missing code or state"),
            status_code=400,
        )
    
    token = await oauth_service.exchange_jira_code(code, state)
    
    if not token:
        return HTMLResponse(
            ERROR_HTML.format(error="Failed to exchange authorization code"),
            status_code=400,
        )
    
    logger.info("Jira OAuth successful", user_id=token.user_id)
    return HTMLResponse(SUCCESS_HTML.format(provider="Jira"))


@router.get("/status/{user_id}")
async def get_oauth_status(user_id: str) -> dict:
    """Get OAuth authorization status for a user.
    
    Args:
        user_id: Slack user ID
        
    Returns:
        Authorization status
    """
    auth = await oauth_repository.get_authorization(user_id)
    
    return {
        "user_id": user_id,
        "zoom": {
            "authorized": auth.zoom_authorized,
            "email": auth.zoom_email,
        },
        "microsoft": {
            "authorized": auth.microsoft_authorized,
            "email": auth.microsoft_email,
        },
        "jira": {
            "authorized": auth.jira_authorized,
            "email": auth.jira_email,
        },
    }


@router.delete("/revoke/{user_id}/{provider}")
async def revoke_oauth(user_id: str, provider: str) -> dict:
    """Revoke OAuth authorization for a user.
    
    Args:
        user_id: Slack user ID
        provider: Provider name (zoom, microsoft, jira)
        
    Returns:
        Revocation result
    """
    from app.models.oauth import OAuthProvider
    
    try:
        oauth_provider = OAuthProvider(provider.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    deleted = await oauth_repository.delete_token(user_id, oauth_provider)
    
    return {
        "revoked": deleted,
        "user_id": user_id,
        "provider": provider,
    }
