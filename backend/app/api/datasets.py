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


SAMPLE_GENERATORS = {
    "gsm8k": (_generate_gsm8k_samples, "Grade School Math 8K - sample problems"),
    "mmlu": (_generate_mmlu_samples, "Massive Multitask Language Understanding - sample questions"),
    "humaneval": (_generate_humaneval_samples, "HumanEval - sample coding problems"),
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
