import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.dataset import Dataset, DatasetItem
from app.schemas.dataset import (
    DatasetImportRequest,
    DatasetItemResponse,
    DatasetResponse,
    DatasetUploadItem,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _generate_gsm8k_samples() -> list[dict]:
    """Generate sample GSM8K math word problems."""
    return [
        {
            "prompt": "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?",
            "reference_answer": "#### 18",
        },
        {
            "prompt": "A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?",
            "reference_answer": "#### 3",
        },
        {
            "prompt": "Josh decides to try flipping a house. He buys a house for $80,000 and then puts in $50,000 in repairs. This increased the value of the house by 150%. How much profit did he make?",
            "reference_answer": "#### 70000",
        },
        {
            "prompt": "James decides to run 3 sprints 3 times a week. He runs 60 meters each sprint. How many total meters does he run a week?",
            "reference_answer": "#### 540",
        },
        {
            "prompt": "Every day, Wendi feeds each of her chickens three cups of mixed chicken feed, containing seeds, mealworms and vegetables to help keep them healthy. She gives the chickens their feed in three separate meals. In the morning, she gives her flock of chickens 15 cups of feed. In the afternoon, she gives her chickens another 25 cups of feed. If each chicken eats 3 cups of feed per day, how many cups of feed does she need to give her chickens in the final meal of the day?",
            "reference_answer": "#### 20",
        },
        {
            "prompt": "Kylar went to the store to get his 2 gallons of whole milk but found that it was out. The store only had 1 gallon of whole milk left, so Kylar decided to just buy it. When he got home, his roommate told him they needed 3 more gallons of milk. How many gallons of milk does Kylar still need to buy?",
            "reference_answer": "#### 4",
        },
        {
            "prompt": "Toulouse has twice as many sheep as Charleston. Charleston has 4 times as many sheep as Seattle. How many sheep do Toulouse, Charleston, and Seattle have together if Seattle has 20 sheep?",
            "reference_answer": "#### 260",
        },
        {
            "prompt": "Carla is downloading a 200 GB file. Normally she can download 2 GB/minute, but 40% of the way through the download, Windows forces a restart to install updates, which takes 20 minutes. Then Carla has to restart the download from the beginning. How long does it take to download the file?",
            "reference_answer": "#### 160",
        },
        {
            "prompt": "John drives for 3 hours at a speed of 60 mph and then turns around because he realizes he forgot something very important at home. He tries to get home in 4 hours but spends the first 2 hours in standstill traffic. He spends the rest of the time driving at 80 mph. How far is he from home when the 4 hours are up?",
            "reference_answer": "#### 20",
        },
        {
            "prompt": "Eliza's rate per hour for the first 40 hours she works each week is $10. She also receives an overtime pay of 1.2 times her regular hourly rate. If Eliza worked for 45 hours this week, how much are her earnings for this week?",
            "reference_answer": "#### 460",
        },
    ]


def _generate_mmlu_samples() -> list[dict]:
    """Generate sample MMLU multiple choice questions."""
    return [
        {
            "prompt": "What is the capital of France?\nA) London\nB) Berlin\nC) Paris\nD) Madrid",
            "reference_answer": "C",
            "metadata": {"subject": "geography"},
        },
        {
            "prompt": "Which planet is known as the Red Planet?\nA) Venus\nB) Mars\nC) Jupiter\nD) Saturn",
            "reference_answer": "B",
            "metadata": {"subject": "astronomy"},
        },
        {
            "prompt": "What is the chemical symbol for gold?\nA) Go\nB) Gd\nC) Au\nD) Ag",
            "reference_answer": "C",
            "metadata": {"subject": "chemistry"},
        },
        {
            "prompt": "Who wrote 'Romeo and Juliet'?\nA) Charles Dickens\nB) William Shakespeare\nC) Jane Austen\nD) Mark Twain",
            "reference_answer": "B",
            "metadata": {"subject": "literature"},
        },
        {
            "prompt": "What is the largest organ in the human body?\nA) Heart\nB) Brain\nC) Liver\nD) Skin",
            "reference_answer": "D",
            "metadata": {"subject": "biology"},
        },
        {
            "prompt": "In what year did World War II end?\nA) 1943\nB) 1944\nC) 1945\nD) 1946",
            "reference_answer": "C",
            "metadata": {"subject": "history"},
        },
        {
            "prompt": "What is the derivative of x^2?\nA) x\nB) 2x\nC) x^2\nD) 2x^2",
            "reference_answer": "B",
            "metadata": {"subject": "mathematics"},
        },
        {
            "prompt": "Which gas makes up the majority of Earth's atmosphere?\nA) Oxygen\nB) Carbon dioxide\nC) Nitrogen\nD) Hydrogen",
            "reference_answer": "C",
            "metadata": {"subject": "earth_science"},
        },
        {
            "prompt": "What is the speed of light approximately?\nA) 3 x 10^6 m/s\nB) 3 x 10^8 m/s\nC) 3 x 10^10 m/s\nD) 3 x 10^12 m/s",
            "reference_answer": "B",
            "metadata": {"subject": "physics"},
        },
        {
            "prompt": "Which of these is NOT a primary color of light?\nA) Red\nB) Green\nC) Blue\nD) Yellow",
            "reference_answer": "D",
            "metadata": {"subject": "physics"},
        },
    ]


def _generate_humaneval_samples() -> list[dict]:
    """Generate sample HumanEval coding problems."""
    return [
        {
            "prompt": "Write a Python function `add(a, b)` that returns the sum of two numbers.",
            "reference_answer": "def add(a, b):\n    return a + b",
            "metadata": {
                "test_cases": "assert add(1, 2) == 3\nassert add(-1, 1) == 0\nassert add(0, 0) == 0"
            },
        },
        {
            "prompt": "Write a Python function `factorial(n)` that returns the factorial of a non-negative integer n.",
            "reference_answer": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
            "metadata": {
                "test_cases": "assert factorial(0) == 1\nassert factorial(1) == 1\nassert factorial(5) == 120\nassert factorial(10) == 3628800"
            },
        },
        {
            "prompt": "Write a Python function `is_palindrome(s)` that returns True if the string s is a palindrome, False otherwise. Ignore case.",
            "reference_answer": "def is_palindrome(s):\n    s = s.lower()\n    return s == s[::-1]",
            "metadata": {
                "test_cases": "assert is_palindrome('racecar') == True\nassert is_palindrome('hello') == False\nassert is_palindrome('Madam') == True"
            },
        },
        {
            "prompt": "Write a Python function `fibonacci(n)` that returns the nth Fibonacci number (0-indexed, where fib(0)=0, fib(1)=1).",
            "reference_answer": "def fibonacci(n):\n    if n <= 0:\n        return 0\n    if n == 1:\n        return 1\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b",
            "metadata": {
                "test_cases": "assert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(10) == 55\nassert fibonacci(6) == 8"
            },
        },
        {
            "prompt": "Write a Python function `flatten(lst)` that takes a nested list and returns a flat list containing all elements.",
            "reference_answer": "def flatten(lst):\n    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result",
            "metadata": {
                "test_cases": "assert flatten([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]\nassert flatten([]) == []\nassert flatten([[1], [2], [3]]) == [1, 2, 3]"
            },
        },
    ]


def _generate_tool_use_samples() -> list[dict]:
    """Generate sample tool use evaluation problems."""
    return [
        {
            "prompt": "You have access to the following tools:\n- search(query: str) - Search the web\n- calculator(expression: str) - Evaluate a math expression\n- weather(city: str) - Get current weather\n\nWhat is the current weather in Tokyo?",
            "reference_answer": json.dumps({"tool_name": "weather", "parameters": {"city": "Tokyo"}}),
        },
        {
            "prompt": "You have access to the following tools:\n- search(query: str) - Search the web\n- calculator(expression: str) - Evaluate a math expression\n- send_email(to: str, subject: str, body: str) - Send an email\n\nCalculate (25 * 4) + 17.",
            "reference_answer": json.dumps({"tool_name": "calculator", "parameters": {"expression": "(25 * 4) + 17"}}),
        },
        {
            "prompt": "You have access to the following tools:\n- read_file(path: str) - Read a file\n- write_file(path: str, content: str) - Write to a file\n- list_dir(path: str) - List directory contents\n\nShow me all files in the /home/user/projects directory.",
            "reference_answer": json.dumps({"tool_name": "list_dir", "parameters": {"path": "/home/user/projects"}}),
        },
        {
            "prompt": "You have access to the following tools:\n- create_task(title: str, priority: str) - Create a new task\n- list_tasks(status: str) - List tasks by status\n- complete_task(task_id: str) - Mark a task as complete\n\nCreate a high priority task called 'Fix login bug'.",
            "reference_answer": json.dumps({"tool_name": "create_task", "parameters": {"title": "Fix login bug", "priority": "high"}}),
        },
        {
            "prompt": "You have access to the following tools:\n- search(query: str) - Search the web\n- translate(text: str, target_lang: str) - Translate text\n- summarize(text: str, max_length: int) - Summarize text\n\nTranslate 'Hello, how are you?' to Spanish.",
            "reference_answer": json.dumps({"tool_name": "translate", "parameters": {"text": "Hello, how are you?", "target_lang": "Spanish"}}),
        },
        {
            "prompt": "You have access to the following tools:\n- get_stock_price(symbol: str) - Get current stock price\n- get_exchange_rate(from_currency: str, to_currency: str) - Get exchange rate\n- portfolio_summary(user_id: str) - Get portfolio summary\n\nWhat is the exchange rate from USD to EUR?",
            "reference_answer": json.dumps({"tool_name": "get_exchange_rate", "parameters": {"from_currency": "USD", "to_currency": "EUR"}}),
        },
        {
            "prompt": "You have access to the following tools:\n- database_query(sql: str) - Run a SQL query\n- create_backup(db_name: str) - Create a database backup\n- restore_backup(backup_id: str) - Restore from backup\n\nBack up the 'production' database before we make changes.",
            "reference_answer": json.dumps({"tool_name": "create_backup", "parameters": {"db_name": "production"}}),
        },
    ]


def _generate_multi_step_samples() -> list[dict]:
    """Generate sample multi-step planning evaluation problems."""
    return [
        {
            "prompt": "You need to deploy a new version of a web application. Describe the steps you would take.",
            "reference_answer": json.dumps({
                "steps": [
                    "Run the test suite to ensure all tests pass",
                    "Build the production artifacts",
                    "Create a backup of the current production state",
                    "Deploy the new version to a staging environment",
                    "Verify the staging deployment works correctly",
                    "Deploy to production",
                    "Monitor logs and metrics for errors",
                ],
                "key_steps": ["test", "build", "backup", "deploy", "monitor"],
            }),
            "metadata": {"strict_order": True},
        },
        {
            "prompt": "A user reports they cannot log in to their account. Walk through the debugging steps.",
            "reference_answer": json.dumps({
                "steps": [
                    "Verify the user's credentials are correct",
                    "Check if the account is locked or disabled",
                    "Review authentication service logs for errors",
                    "Test the login endpoint directly",
                    "Check database connectivity",
                    "Verify session/token management is working",
                ],
                "key_steps": ["credentials", "account", "logs", "endpoint", "database"],
            }),
        },
        {
            "prompt": "Plan the steps to set up a CI/CD pipeline for a new microservice.",
            "reference_answer": json.dumps({
                "steps": [
                    "Set up a version control repository",
                    "Write unit and integration tests",
                    "Create a Dockerfile for the service",
                    "Configure the CI pipeline to run tests on push",
                    "Add build and push steps for the Docker image",
                    "Set up staging and production deployment environments",
                    "Configure automated deployment on merge to main",
                ],
                "key_steps": ["repository", "tests", "Docker", "CI pipeline", "deployment"],
            }),
            "metadata": {"strict_order": True},
        },
        {
            "prompt": "Describe the steps to migrate a database from PostgreSQL to a new schema version.",
            "reference_answer": json.dumps({
                "steps": [
                    "Review the schema changes required",
                    "Write migration scripts",
                    "Test migrations on a copy of the database",
                    "Create a full backup of the production database",
                    "Schedule a maintenance window",
                    "Run the migration scripts",
                    "Verify data integrity after migration",
                    "Update application code if needed",
                ],
                "key_steps": ["migration scripts", "backup", "test", "verify", "maintenance"],
            }),
        },
        {
            "prompt": "A web page is loading very slowly. Outline the steps to diagnose and fix the performance issue.",
            "reference_answer": json.dumps({
                "steps": [
                    "Open browser developer tools and check network tab",
                    "Identify slow requests and large assets",
                    "Check server response times",
                    "Profile JavaScript execution",
                    "Review database queries for N+1 or slow queries",
                    "Implement fixes like caching, lazy loading, or query optimization",
                    "Measure performance improvements",
                ],
                "key_steps": ["developer tools", "network", "server", "database", "caching"],
            }),
        },
    ]


def _generate_react_samples() -> list[dict]:
    """Generate sample ReAct reasoning evaluation problems."""
    return [
        {
            "prompt": "You have access to: search(query), calculator(expr), lookup(term).\n\nQuestion: What is the population of France divided by the population of Belgium? Use the ReAct format (Thought/Action/Observation) to solve this.",
            "reference_answer": json.dumps({
                "expected_action": "calculator(67000000 / 11500000)",
                "key_concepts": ["population", "France", "Belgium", "search", "calculator"],
            }),
            "metadata": {"min_reasoning_steps": 2},
        },
        {
            "prompt": "You have access to: search(query), read_file(path), write_file(path, content).\n\nTask: Find the error in /app/config.json and fix it. The application is crashing on startup with 'Invalid JSON'. Use ReAct format.",
            "reference_answer": json.dumps({
                "expected_action": "write_file(/app/config.json",
                "key_concepts": ["read_file", "JSON", "parse", "syntax", "fix"],
            }),
            "metadata": {"min_reasoning_steps": 2},
        },
        {
            "prompt": "You have access to: search(query), get_weather(city), send_message(user, text).\n\nTask: Check if it will rain in London tomorrow and notify user Alice if so. Use ReAct format.",
            "reference_answer": json.dumps({
                "expected_action": "send_message(Alice",
                "key_concepts": ["weather", "London", "rain", "Alice", "notify"],
            }),
            "metadata": {"min_reasoning_steps": 2},
        },
        {
            "prompt": "You have access to: database_query(sql), search(query), calculator(expr).\n\nTask: Find the average order value for customers in the US from the orders table. Use ReAct format.",
            "reference_answer": json.dumps({
                "expected_action": "database_query(SELECT AVG",
                "key_concepts": ["database", "query", "AVG", "orders", "US"],
            }),
            "metadata": {"min_reasoning_steps": 1},
        },
        {
            "prompt": "You have access to: list_files(dir), read_file(path), grep(pattern, path).\n\nTask: Find all Python files in /src that import the 'requests' library. Use ReAct format.",
            "reference_answer": json.dumps({
                "expected_action": "grep(import requests",
                "key_concepts": ["list_files", "grep", "Python", "requests", "import"],
            }),
            "metadata": {"min_reasoning_steps": 1},
        },
    ]


def _generate_instruction_following_samples() -> list[dict]:
    """Generate sample instruction following evaluation problems."""
    return [
        {
            "prompt": "List 3 benefits of exercise. Your response must be in JSON format with a key 'benefits' containing an array. Keep your response under 500 characters.",
            "reference_answer": json.dumps({
                "constraints": [
                    {"type": "format", "check": "json"},
                    {"type": "contains", "check": "benefits"},
                    {"type": "length_max", "check": 500},
                ],
            }),
        },
        {
            "prompt": "Write a short poem about the ocean. It must start with 'The waves' and end with a period. Do not mention the word 'blue'.",
            "reference_answer": json.dumps({
                "constraints": [
                    {"type": "starts_with", "check": "The waves"},
                    {"type": "ends_with", "check": "."},
                    {"type": "excludes", "check": "blue"},
                ],
            }),
        },
        {
            "prompt": "Generate a CSV table of 3 programming languages with columns: name, year_created, paradigm. Do not include JavaScript.",
            "reference_answer": json.dumps({
                "constraints": [
                    {"type": "format", "check": "csv"},
                    {"type": "contains", "check": "name"},
                    {"type": "contains", "check": "year_created"},
                    {"type": "excludes", "check": "JavaScript"},
                ],
            }),
        },
        {
            "prompt": "Explain what an API is in exactly one paragraph. Your response must contain the word 'interface' and 'request'. It must be at least 100 characters.",
            "reference_answer": json.dumps({
                "constraints": [
                    {"type": "contains", "check": "interface"},
                    {"type": "contains", "check": "request"},
                    {"type": "length_min", "check": 100},
                ],
            }),
        },
        {
            "prompt": "Write a product description for a laptop. Use markdown formatting with at least one heading. Do not exceed 1000 characters. Include the word 'performance'.",
            "reference_answer": json.dumps({
                "constraints": [
                    {"type": "format", "check": "markdown"},
                    {"type": "contains", "check": "performance"},
                    {"type": "length_max", "check": 1000},
                ],
            }),
        },
        {
            "prompt": "List 5 countries and their capitals. Format your answer as XML with <country> elements containing <name> and <capital> tags. Do not include the United States.",
            "reference_answer": json.dumps({
                "constraints": [
                    {"type": "format", "check": "xml"},
                    {"type": "contains", "check": "<country>"},
                    {"type": "contains", "check": "<capital>"},
                    {"type": "excludes", "check": "United States"},
                ],
            }),
        },
    ]


def _generate_api_interaction_samples() -> list[dict]:
    """Generate sample API interaction evaluation problems."""
    return [
        {
            "prompt": "Construct an API call to create a new user with name 'John Doe' and email 'john@example.com' using the REST API at https://api.example.com/users.",
            "reference_answer": json.dumps({
                "method": "POST",
                "endpoint": "https://api.example.com/users",
                "required_headers": {"Content-Type": "application/json"},
                "body": {"name": "John Doe", "email": "john@example.com"},
            }),
        },
        {
            "prompt": "Write an API call to fetch all active products from https://api.shop.com/products?status=active. Include an Authorization header with Bearer token 'abc123'.",
            "reference_answer": json.dumps({
                "method": "GET",
                "endpoint": "https://api.shop.com/products?status=active",
                "required_headers": {"Authorization": "Bearer abc123"},
                "body": None,
            }),
        },
        {
            "prompt": "Construct a DELETE request to remove order #456 at https://api.example.com/orders/456. Include an X-API-Key header with value 'secret-key'.",
            "reference_answer": json.dumps({
                "method": "DELETE",
                "endpoint": "https://api.example.com/orders/456",
                "required_headers": {"X-API-Key": "secret-key"},
                "body": None,
            }),
        },
        {
            "prompt": "Write an API call to update the price of product ID 789 to $29.99 at https://api.store.com/products/789. Use JSON content type.",
            "reference_answer": json.dumps({
                "method": "PUT",
                "endpoint": "https://api.store.com/products/789",
                "required_headers": {"Content-Type": "application/json"},
                "body": {"price": 29.99},
            }),
        },
        {
            "prompt": "Construct a PATCH request to update only the status field to 'shipped' for order #123 at https://api.example.com/orders/123.",
            "reference_answer": json.dumps({
                "method": "PATCH",
                "endpoint": "https://api.example.com/orders/123",
                "required_headers": {"Content-Type": "application/json"},
                "body": {"status": "shipped"},
            }),
        },
        {
            "prompt": "Write an API call to search for users with the query 'admin' using https://api.example.com/users/search. Pass the query as a JSON body with key 'q'.",
            "reference_answer": json.dumps({
                "method": "POST",
                "endpoint": "https://api.example.com/users/search",
                "required_headers": {"Content-Type": "application/json"},
                "body": {"q": "admin"},
            }),
        },
    ]


def _generate_error_recovery_samples() -> list[dict]:
    """Generate sample error recovery evaluation problems."""
    return [
        {
            "prompt": "You ran the following code and got an error:\n\n```python\ndata = json.loads(response.text)\nuser = data['users'][0]['name']\n```\n\nError: `KeyError: 'users'`\n\nThe API response was: `{\"results\": [{\"name\": \"Alice\"}]}`\n\nIdentify the error and provide the fix.",
            "reference_answer": json.dumps({
                "error_detected": True,
                "diagnosis_keywords": ["KeyError", "users", "results", "key"],
                "action_keywords": ["results", "data['results']", "replace"],
                "explanation_keywords": ["key", "users", "results", "response"],
            }),
        },
        {
            "prompt": "A database connection keeps failing with: `OperationalError: too many connections`\n\nThe application opens a new connection for each request but never closes them.\n\nDiagnose the issue and suggest a fix.",
            "reference_answer": json.dumps({
                "error_detected": True,
                "diagnosis_keywords": ["connection", "close", "leak", "pool"],
                "action_keywords": ["connection pool", "close", "context manager"],
                "explanation_keywords": ["connection", "limit", "resource"],
            }),
        },
        {
            "prompt": "The following API call returns a 403 Forbidden error:\n\n```\ncurl -X GET https://api.example.com/admin/users \\\n  -H 'Authorization: Bearer user_token_123'\n```\n\nThe token belongs to a regular user. What's wrong and how do you fix it?",
            "reference_answer": json.dumps({
                "error_detected": True,
                "diagnosis_keywords": ["permission", "403", "admin", "authorization"],
                "action_keywords": ["admin", "token", "role", "permission"],
                "explanation_keywords": ["access", "privilege", "role"],
            }),
        },
        {
            "prompt": "A Python script crashes with:\n\n```\nTypeError: unsupported operand type(s) for +: 'int' and 'str'\n```\n\nThe code is: `total = count + input('Enter amount: ')`\n\nWhat's the error and how should it be fixed?",
            "reference_answer": json.dumps({
                "error_detected": True,
                "diagnosis_keywords": ["TypeError", "int", "str", "type"],
                "action_keywords": ["int(", "convert", "cast"],
                "explanation_keywords": ["type", "string", "integer", "convert"],
            }),
        },
        {
            "prompt": "A deployed service keeps restarting. The logs show:\n\n```\nOOM Killed: process used 2.1GB, limit is 512MB\n```\n\nThe service loads a large CSV file entirely into memory on startup.\n\nDiagnose and suggest a recovery strategy.",
            "reference_answer": json.dumps({
                "error_detected": True,
                "diagnosis_keywords": ["memory", "OOM", "CSV", "limit"],
                "action_keywords": ["stream", "chunk", "batch", "memory limit", "increase"],
                "explanation_keywords": ["memory", "load", "file", "resource"],
            }),
        },
        {
            "prompt": "A cron job that sends daily reports stopped working. Investigation shows:\n\n```\nsmtplib.SMTPAuthenticationError: (535, 'Authentication failed')\n```\n\nThe email password was recently rotated but the cron job config was not updated.\n\nIdentify the issue and provide the fix.",
            "reference_answer": json.dumps({
                "error_detected": True,
                "diagnosis_keywords": ["password", "authentication", "credential", "rotated"],
                "action_keywords": ["update", "password", "credential", "config"],
                "explanation_keywords": ["password", "rotation", "config", "authentication"],
            }),
        },
    ]


SAMPLE_GENERATORS = {
    "gsm8k": (_generate_gsm8k_samples, "Grade School Math 8K - sample problems"),
    "mmlu": (_generate_mmlu_samples, "Massive Multitask Language Understanding - sample questions"),
    "humaneval": (_generate_humaneval_samples, "HumanEval - sample coding problems"),
    "tool_use": (_generate_tool_use_samples, "Tool Use - Agent tool selection & invocation"),
    "multi_step": (_generate_multi_step_samples, "Multi-Step Planning - Task decomposition"),
    "react": (_generate_react_samples, "ReAct Reasoning - Thought-action-observation"),
    "instruction_following": (_generate_instruction_following_samples, "Instruction Following - Multi-constraint compliance"),
    "api_interaction": (_generate_api_interaction_samples, "API Interaction - Correct API call construction"),
    "error_recovery": (_generate_error_recovery_samples, "Error Recovery - Error handling & adaptation"),
}


def _dataset_to_response(dataset: Dataset) -> DatasetResponse:
    """Convert a Dataset model to a DatasetResponse, handling metadata."""
    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        dataset_type=dataset.dataset_type,
        description=dataset.description,
        total_items=dataset.total_items,
        created_at=dataset.created_at,
    )


def _item_to_response(item: DatasetItem) -> DatasetItemResponse:
    """Convert a DatasetItem model to a DatasetItemResponse."""
    metadata = {}
    if item.metadata_:
        if isinstance(item.metadata_, str):
            try:
                metadata = json.loads(item.metadata_)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        else:
            metadata = item.metadata_
    return DatasetItemResponse(
        id=item.id,
        dataset_id=item.dataset_id,
        item_index=item.item_index,
        prompt=item.prompt,
        reference_answer=item.reference_answer,
        metadata=metadata,
    )


@router.get("/", response_model=list[DatasetResponse])
async def list_datasets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    datasets = result.scalars().all()
    return [_dataset_to_response(d) for d in datasets]


@router.post("/import", response_model=DatasetResponse)
async def import_dataset(request: DatasetImportRequest, db: AsyncSession = Depends(get_db)):
    source = request.source.lower()

    if source not in SAMPLE_GENERATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown dataset source: {request.source}. Available: {list(SAMPLE_GENERATORS.keys())}",
        )

    # Check if dataset already exists
    existing = await db.execute(select(Dataset).where(Dataset.name == source))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Dataset '{source}' already exists")

    generator_fn, description = SAMPLE_GENERATORS[source]
    samples = generator_fn()

    # Apply max_items limit
    if request.max_items and request.max_items < len(samples):
        samples = samples[: request.max_items]

    # Create dataset
    dataset = Dataset(
        name=source,
        dataset_type=source,
        description=description,
        total_items=len(samples),
        metadata_=json.dumps({"split": request.split, "subset": request.subset}),
    )
    db.add(dataset)
    await db.flush()

    # Create items
    for idx, sample in enumerate(samples):
        item_metadata = sample.get("metadata", {})
        item = DatasetItem(
            dataset_id=dataset.id,
            item_index=idx,
            prompt=sample["prompt"],
            reference_answer=sample.get("reference_answer"),
            metadata_=json.dumps(item_metadata),
        )
        db.add(item)

    await db.flush()
    await db.refresh(dataset)
    return _dataset_to_response(dataset)


@router.post("/upload", response_model=DatasetResponse)
async def upload_dataset(
    name: str,
    dataset_type: str = "custom",
    description: Optional[str] = None,
    items: list[DatasetUploadItem] = [],
    db: AsyncSession = Depends(get_db),
):
    if not items:
        raise HTTPException(status_code=400, detail="No items provided")

    # Check if dataset already exists
    existing = await db.execute(select(Dataset).where(Dataset.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Dataset '{name}' already exists")

    dataset = Dataset(
        name=name,
        dataset_type=dataset_type,
        description=description,
        total_items=len(items),
        metadata_=json.dumps({}),
    )
    db.add(dataset)
    await db.flush()

    for idx, upload_item in enumerate(items):
        item = DatasetItem(
            dataset_id=dataset.id,
            item_index=idx,
            prompt=upload_item.prompt,
            reference_answer=upload_item.reference_answer,
            metadata_=json.dumps(upload_item.metadata),
        )
        db.add(item)

    await db.flush()
    await db.refresh(dataset)
    return _dataset_to_response(dataset)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _dataset_to_response(dataset)


@router.get("/{dataset_id}/items", response_model=list[DatasetItemResponse])
async def get_dataset_items(
    dataset_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    result = await db.execute(
        select(DatasetItem)
        .where(DatasetItem.dataset_id == dataset_id)
        .order_by(DatasetItem.item_index)
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return [_item_to_response(item) for item in items]


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await db.delete(dataset)
    return {"detail": "Dataset deleted"}
