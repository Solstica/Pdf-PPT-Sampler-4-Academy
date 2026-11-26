# Synthetic demo

Run `python examples/synthetic_demo.py .tests/demo`, then `academy --workspace .tests/demo ingest`, `render`, `validate`, `progress`, `batch --document L01 --size 3` and `print --pages L01-P001,H01-P003` using the same workspace flag. The generator creates only invented multilingual text, mathematical superscript, vector shapes and a blank page. Generated data is ignored; no real course source is included.
