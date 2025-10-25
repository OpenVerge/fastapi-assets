for version in 3.12 3.13; do
  echo "Testing on Python $version"
  uv run --python $version pytest
done
