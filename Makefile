.PHONY: dev test-ml test-dotnet test-fe deploy-stg

dev:
	docker compose up --build

test-ml:
	@if [ -d services/ml-backend/tests ]; then \
		cd services/ml-backend && uv run pytest tests/ -v; \
	else \
		echo "services/ml-backend has no tests yet -- see services/ml-backend/CLAUDE.md"; \
	fi

test-dotnet:
	@if [ -f services/decision-engine/*.sln ]; then \
		cd services/decision-engine && dotnet test; \
	else \
		echo "services/decision-engine has no project yet -- see services/decision-engine/CLAUDE.md"; \
	fi

test-fe:
	@if [ -f frontend/package.json ] && grep -q '"test"' frontend/package.json; then \
		cd frontend && pnpm test; \
	else \
		echo "frontend has no test script yet -- see frontend/CLAUDE.md"; \
	fi

deploy-stg:
	helm upgrade --install self-healing-framework ./infrastructure/helm/self-healing-framework \
		--namespace selfheal-system --create-namespace \
		-f infrastructure/helm/self-healing-framework/values.yaml
