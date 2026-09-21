check:
	ruff format --check .
	ruff check .
	pytest

charts:
	python -m gridpulse.charts render --out docs/images

site:
	python -m gridpulse.charts site --out build/site
