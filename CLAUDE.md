# CLAUDE.md: Development Guide for news-suck

## Build and Run Commands
- Start app: `./start.sh` (runs both crawler and webapp)
- Run webapp: `cd webapp && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Run crawler: `cd crawler && PYTHONPATH=. python app/main.py`
- Install deps: `pip install -r webapp/requirements.txt -r crawler/requirements.txt`

## Code Style Guidelines
- **Imports**: Group imports (stdlib, third-party, local) with stdlib first
- **Formatting**: 4-space indentation, 120 char line limit
- **Types**: Use type annotations for function parameters and return values
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Error handling**: Use try/except with specific exception types
- **Documentation**: Docstrings for classes and non-trivial functions
- **Structure**: Follow established pattern of models, services, routes directories
- **Database**: SQLAlchemy ORM with Pydantic models for API responses