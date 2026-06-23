# RadioSense API Contract

Backend base URL:
http://127.0.0.1:8081

Frontend env:
VITE_RADIO_API_BASE_URL=

Routes:
- GET /api/health
- GET /api/stations?limit=100
- GET /api/detections
- GET /api/memory/summary
- GET /api/harvest/status
- POST /api/harvest/probe
- POST /api/harvest/start
- POST /api/harvest/stop

Rule:
Frontend must not assume DB structure directly.
Backend API is the only contract.