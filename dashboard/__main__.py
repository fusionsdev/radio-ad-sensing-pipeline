"""Run dashboard: python -m dashboard"""

from __future__ import annotations

import uvicorn

from shared.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "dashboard.main:create_app",
        factory=True,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
