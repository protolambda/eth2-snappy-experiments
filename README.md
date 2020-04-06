# Snappy experiment

Some example code to run Rumor and Pyrum, and script some RPC Eth2 snappy-compression requests/responses.

## Install/Running

Pre-requisite: Rumor, go install it. You can run from source, just modify the `Rumor(cmd=...)` that is used in the `experiment.py`

```sh
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt

python make_genesis.py

python experiment.py
```

## License

MIT, see [`LICENSE`](./LICENSE) file.
