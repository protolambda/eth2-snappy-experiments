import trio
import os
import io
from typing import Coroutine, Callable

from pyrum import Rumor, SubprocessConn


# Before importing spec, load config:
# from eth2spec.config.config_util import prepare_config
# prepare_config("./some-dir", "config-name")

from eth2spec.phase0.spec import *


class Status(Container):
    version: Bytes4
    finalized_root: Bytes32
    finalized_epoch: uint64
    head_root: Bytes32
    head_slot: uint64


class Goodbye(uint64):
    pass


class BlocksByRange(Container):
    head_block_root: Bytes32
    start_slot: uint64
    count: uint64
    step: uint64


class BlocksByRoot(List[SignedBeaconBlock, 1024]):
    pass


def load_state(filepath: str) -> BeaconState:
    state_size = os.stat(filepath).st_size
    with io.open(filepath, 'br') as f:
        return BeaconState.deserialize(f, state_size)


async def basic_status_example(rumor: Rumor, nursery: trio.Nursery):

    # Load some genesis state of the client (or use make_genesis.py)
    state = load_state('genesis.ssz')

    # Morty is us
    morty = rumor.actor('morty')
    await morty.host.start()
    await morty.host.listen(tcp=9000)
    print("started morty")

    # Rick is the other client
    rick_enr = "enr:-Iu4QGuiaVXBEoi4kcLbsoPYX7GTK9ExOODTuqYBp9CyHN_PSDtnLMCIL91ydxUDRPZ-jem-o0WotK6JoZjPQWhTfEsTgmlkgnY0gmlwhDbOLfeJc2VjcDI1NmsxoQLVqNEoCVTC74VmUx25USyFe7lL0TgpXHaCX9CDy9H6boN0Y3CCIyiDdWRwgiMo"

    rick_peer_id = await morty.peer.connect(rick_enr, "bootnode").peer_id()

    print(f"connected to Rick {rick_peer_id}")

    print("Testing a Status RPC request")

    genesis_root = state.hash_tree_root()

    # Sync status
    morty_status = Status(
        version=GENESIS_FORK_VERSION,
        finalized_root=genesis_root,
        finalized_epoch=0,
        head_root=genesis_root,
        head_epoch=0,
    )

    req = morty_status.encode_bytes().hex()
    print(f"morty: sending rick a status request: {req}")

    # Note: public testnet node is not updated, only receiving an empty response if snappy is enabled.
    resp = await morty.rpc.status.req.raw(rick_peer_id, req, raw=True)

    print(f"morty: received status response from rick: {resp}")
    try:
        rick_status = Status.decode_bytes(bytes.fromhex(resp['chunk']['data']))
        print(rick_status)
    except Exception as e:
        print(f"could not decode status response: {e}")

    call = morty.rpc.status.listen(raw=True, compression='snappy')
    # Other keywords to try here:
    # Req-resp timeout: timeout=123000 (in milliseconds, 0 to disable)
    # Drop contents, not keeping track of them to reply later: drop=True
    # Ignore request bytes, do not read any: read=False

    async def process_requests():
        async for req in call.req():
            print(f"morty: Got request: {req}")

            # Respond with Input error
            # await morty.rpc.status.resp.invalid_request(req['req_id'], f"hello! Morty does not like your request!")

            # Respond with server error
            # await morty.rpc.status.resp.server_error(req['req_id'], f"hello! Morty failed, look for a new morty!")

            # Respond with valid chunk (and done=True to exit immediately after)
            resp = morty_status.encode_bytes().hex()
            await morty.rpc.status.resp.chunk.raw(req['req_id'], resp, done=True)

            # Or send arbitrary data
            # resp = bytes.fromhex('1337')
            # await morty.rpc.status.resp.chunk.raw(req['req_id'], resp, result_code=2, done=True)

        print("morty: stopped listening for requests")

    print("listening for requests")
    await process_requests()

    # Or start listening in the background:
    # nursery.start_soon(process_requests)
    # await call.started()  # wait for the stream handler to come online, there will be a "started=true" entry.


async def server_blocks_by_range_example(rumor: Rumor, nursery: trio.Nursery):

    # Morty is us
    morty = rumor.actor('morty')
    await morty.host.start()
    await morty.host.listen(tcp=9000)
    print("started morty")

    # Rick is the other client
    rick_enr = "enr:-Iu4QGuiaVXBEoi4kcLbsoPYX7GTK9ExOODTuqYBp9CyHN_PSDtnLMCIL91ydxUDRPZ-jem-o0WotK6JoZjPQWhTfEsTgmlkgnY0gmlwhDbOLfeJc2VjcDI1NmsxoQLVqNEoCVTC74VmUx25USyFe7lL0TgpXHaCX9CDy9H6boN0Y3CCIyiDdWRwgiMo"

    rick_peer_id = await morty.peer.connect(rick_enr, "bootnode").peer_id()

    print(f"connected to Rick {rick_peer_id}")

    call = morty.rpc.blocks_by_range.listen(raw=True, compression='snappy')

    print("listening for requests")

    async for req in call.req():
        print(f"morty: Got request: {req}")

        parsed_req = BlocksByRange.decode_bytes(bytes.fromhex(req['chunk']['data']))
        print('parsed request: ', parsed_req)

        start = parsed_req.start_slot
        end = start + parsed_req.count * parsed_req.step

        for i, slot in zip(range(parsed_req.count), range(start, end, parsed_req.step)):
            # Try any message:
            # resp = f"not a block, but can you decode this chunk though? chunk nr {i} here".encode()
            # Or construct a block (can make it more consensus-valid, but snappy compression testing can be simple):
            resp = SignedBeaconBlock(message=BeaconBlock(slot=slot)).encode_bytes().hex()
            print(f"responding chunk {i} slot {slot} chunk: {resp}")
            await morty.rpc.blocks_by_range.resp.chunk.raw(req['req_id'], resp, done=(i + 1 == parsed_req.count))

        print("done responding")

    print("morty: stopped listening for requests")


async def server_blocks_by_root_example(rumor: Rumor, nursery: trio.Nursery):

    # Morty is us
    morty = rumor.actor('morty')
    await morty.host.start()
    await morty.host.listen(tcp=9000)
    print("started morty")

    # Rick is the other client
    rick_enr = "enr:-Iu4QGuiaVXBEoi4kcLbsoPYX7GTK9ExOODTuqYBp9CyHN_PSDtnLMCIL91ydxUDRPZ-jem-o0WotK6JoZjPQWhTfEsTgmlkgnY0gmlwhDbOLfeJc2VjcDI1NmsxoQLVqNEoCVTC74VmUx25USyFe7lL0TgpXHaCX9CDy9H6boN0Y3CCIyiDdWRwgiMo"

    rick_peer_id = await morty.peer.connect(rick_enr, "bootnode").peer_id()

    print(f"connected to Rick {rick_peer_id}")

    call = morty.rpc.blocks_by_root.listen(raw=True, compression='snappy')

    print("listening for requests")

    async for req in call.req():
        print(f"morty: Got request: {req}")

        parsed_req = BlocksByRoot.decode_bytes(bytes.fromhex(req['chunk']['data']))
        print('parsed request: ', parsed_req)

        for i, root in enumerate(parsed_req):
            resp = SignedBeaconBlock(message=BeaconBlock(slot=slot)).encode_bytes().hex()
            print(f"responding chunk {i} root {root}, chunk: {resp}")
            await morty.rpc.blocks_by_range.resp.chunk.raw(req['req_id'], resp, done=(i + 1 == len(parsed_req)))

        print("done responding")

    print("morty: stopped listening for requests")


async def run_rumor_function(fn: Callable[[Rumor, trio.Nursery], Coroutine]):
    async with trio.open_nursery() as nursery:
        try:
            async with SubprocessConn(cmd='cd ../rumor && go run . bare') as conn:
                # A Trio nursery hosts all the async tasks of the Rumor instance.
                async with trio.open_nursery() as nursery:
                    # And optionally use Rumor(conn, debug=True) to be super verbose about Rumor communication.
                    await fn(Rumor(conn, nursery), nursery)
                    # Cancel the nursery to signal that we are not using Rumor anymore
                    nursery.cancel_scope.cancel()
        except Exception as e:
            print(e)


trio.run(run_rumor_function, basic_status_example)
# trio.run(run_rumor_function, server_blocks_by_range_example)
# trio.run(run_rumor_function, server_blocks_by_root_example)
