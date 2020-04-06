import io
import time

# Before importing spec, load config:
# from eth2spec.config.config_util import prepare_config
# prepare_config("./some-dir", "config-name")

from eth2spec.phase0.spec import *
from eth2spec.phase0 import spec

from eth2spec.test.helpers.deposits import prepare_genesis_deposits

# Hack to disable BLS, no need for verification of deposits here.
spec.bls.bls_active = False

eth1_block_hash = b'\x12' * 32
eth1_timestamp = uint64(int(time.time()) + 60)  # a minute from now

print(f"creating state! genesis time: {eth1_timestamp}")

deposits, deposit_root, _ = prepare_genesis_deposits(spec,
                                                     200,  # Just 200 validators, lazy
                                                     MAX_EFFECTIVE_BALANCE,
                                                     signed=True)

state = initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

print("writing state!")

with io.open('genesis.ssz', 'wb') as w:
    state.serialize(w)

print("done!")
