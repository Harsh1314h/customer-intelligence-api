from pathlib import Path

from app.ml.demo import create_demo_artifacts


if __name__ == "__main__":
    create_demo_artifacts(Path("models"))
    print("Demo artifacts written to models/")
