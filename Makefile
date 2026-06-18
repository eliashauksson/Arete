PID_FILE := .server.pid
PORT     := 8000
LOG_FILE := .server.log

.PHONY: start stop reload

start:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Server already running (PID $$(cat $(PID_FILE)))"; \
	else \
		python -m uvicorn app.main:app --port $(PORT) > $(LOG_FILE) 2>&1 & \
		echo $$! > $(PID_FILE); \
		echo "Server started on http://localhost:$(PORT) (PID $$(cat $(PID_FILE)))"; \
	fi

stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		kill $$(cat $(PID_FILE)) && rm -f $(PID_FILE); \
		echo "Server stopped"; \
	else \
		echo "Server not running"; \
		rm -f $(PID_FILE); \
	fi

reload: stop start
