from fastapi import APIRouter, Request, Response
import httpx

router = APIRouter(prefix="/speech-to-text/job/v1", tags=["compat"])


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])  
async def proxy(path: str, request: Request):
    """
    Proxy incoming requests from /speech-to-text/job/v1/... to internal /api/... endpoints.
    This is a lightweight developer convenience; for production consider configuring a
    proper reverse proxy or implementing direct handler mappings.
    """
    # Map to internal API prefix
    target_url = f"http://127.0.0.1:8000/api/{path}"

    # Copy headers except Host to avoid confusion
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}

    body = await request.body()

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params,
            timeout=60.0,
        )

    # Filter hop-by-hop headers
    excluded = {
        "transfer-encoding",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "upgrade",
    }
    response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

    return Response(content=resp.content, status_code=resp.status_code, headers=response_headers)
