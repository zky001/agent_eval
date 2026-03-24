.PHONY: dev backend frontend install install-backend install-frontend clean

# Run both backend and frontend concurrently
dev: install
	@echo "Starting backend and frontend..."
	@cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@cd frontend && npm run dev &
	@wait

# Run backend only
backend: install-backend
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend only
frontend: install-frontend
	cd frontend && npm run dev

# Install all dependencies
install: install-backend install-frontend

# Install backend dependencies
install-backend:
	cd backend && pip install -e ".[dev]"

# Install frontend dependencies
install-frontend:
	cd frontend && npm install

# Clean generated files
clean:
	rm -rf backend/data/*.db
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
