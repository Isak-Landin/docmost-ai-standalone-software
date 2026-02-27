
text = """./.env
./.gitkeep
./Dockerfile.single_container.bak
./docmost_fetcher.py
./docker-compose.yml
./.gitignore
./LICENSE
./ui/Dockerfile
./ui/app_ui.py
./ui/__pycache__/app_ui.cpython-312.pyc
./ui/static/js/main.js
./ui/static/js/api.js
./ui/static/js/util.js
./ui/static/js/state.js
./ui/static/js/chat.js
./ui/static/js/tree.js
./ui/static/index.html
./ui/static/css/app.css
./docmost-fetcher/__init__.py
./docmost-fetcher/docmost_fetcher.py
./docmost-fetcher/docmost_fetcher.py.bak
./docmost-fetcher/Dockerfile
./docmost-fetcher/api/__init__.py
./docmost-fetcher/api/routes.py
./docmost-fetcher/api/test_query.py
./docmost-fetcher/api/test_file.py
./docmost-fetcher/api/utils/__init__.py
./docmost-fetcher/api/utils/schema_db_validation_management.py
./docmost-fetcher/api/db_functionality.py
./requirements.txt
./README.md
./container-commands.md
./backend/integrations/__init__.py
./backend/integrations/docmost_client.py
./backend/integrations/ollama_client.py
./backend/__init__.py
./backend/worker/__init__.py
./backend/worker/loop.py
./backend/worker/run_worker.py
./backend/http/__init__.py
./backend/http/routes.py
./backend/prompt/__init__.py
./backend/prompt/prompt_builder.py
./backend/Dockerfile
./backend/app.py
./backend/db/__init__.py
./backend/db/repo.py
./backend/db/session.py
./backend/schemas/__init__.py
./backend/schemas/docmost_db_schemas/__init__.py
./backend/schemas/docmost_db_schemas/single_page_content.json
./backend/init.sql
./logging_config.py
"""

print(text)

for line in text.split("\n"):
    if line.startswith("./backend/"):
        line.strip("./backend/")


    print("###" + line)