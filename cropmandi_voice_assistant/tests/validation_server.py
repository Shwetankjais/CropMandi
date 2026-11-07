"""Optional browser QA server. Rewrites API ports in responses, never source files.

Run from project root with DATABASE_URL set to a read-only database URI:
  python -m uvicorn cropmandi_voice_assistant.tests.validation_server:app --port 8766
"""
from pathlib import Path
from fastapi.responses import Response
from starlette.staticfiles import StaticFiles
from apps.api.main import app

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


class ValidationFrontend(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200 and hasattr(response, "path"):
            source = Path(response.path)
            if source.suffix in (".html", ".js"):
                text = source.read_text().replace("http://127.0.0.1:8001", "http://127.0.0.1:8766")
                return Response(text, media_type="text/html" if source.suffix == ".html" else "application/javascript", headers={"Cache-Control":"no-store"})
        return response


app.mount("/", ValidationFrontend(directory=FRONTEND, html=True), name="voice-validation-frontend")
