import trio
import io
import os

from pyrum import Rumor, SubprocessConn

from eth2spec.phase0.spec import *

# from eth2config.config_util import prepare_config
# from importlib import reload
# # Apply lighthouse config to spec
# prepare_config("./lighthouse", "config")


class Goodbye(uint64):
    pass


class Status(Container):
    version: Bytes4
    finalized_root: Bytes32
    finalized_epoch: uint64
    head_root: Bytes32
    head_slot: uint64


class BlocksByRange(Container):
    head_block_root: Bytes32
    start_slot: uint64
    count: uint64
    step: uint64


def load_state(filepath: str) -> BeaconState:
    state_size = os.stat(filepath).st_size
    with io.open(filepath, 'br') as f:
        return BeaconState.deserialize(f, state_size)


async def sync_experiment(rumor: Rumor):
    state = load_state('genesis.ssz')

    morty = rumor.actor('morty')
    await morty.host.start()
    await morty.host.listen(tcp=9000)

    head = state.latest_block_header.copy()
    head.state_root = state.hash_tree_root()

    # Sync status
    morty_status = Status(
        version=compute_fork_digest(state.fork.current_version, state.genesis_validators_root),
        finalized_root=state.finalized_checkpoint.root,
        finalized_epoch=0,
        head_root=head.hash_tree_root(),
        head_epoch=0,
    )
    print("Morty status:")
    print(morty_status)
    print(morty_status.encode_bytes().hex())

    async def sync_work():
        await trio.sleep(2)

        rick_enr = "enr:-Iu4QGuiaVXBEoi4kcLbsoPYX7GTK9ExOODTuqYBp9CyHN_PSDtnLMCIL91ydxUDRPZ-jem-o0WotK6JoZjPQWhTfEsTgmlkgnY0gmlwhDbOLfeJc2VjcDI1NmsxoQLVqNEoCVTC74VmUx25USyFe7lL0TgpXHaCX9CDy9H6boN0Y3CCIyiDdWRwgiMo"

        peer_id = await morty.peer.connect(rick_enr, "bootnode").peer_id()
        print(f"connected bootnode peer: {peer_id}")

        print(await morty.peer.list('all'))

        async def sync_step(current_slot: Slot):
            slot_count = 20
            range_req = BlocksByRange(start_slot=current_slot + 1, count=slot_count, step=1).encode_bytes().hex()
            print("range req:", range_req)
            blocks = []
            async for chunk in morty.rpc.blocks_by_range.req.raw(peer_id, range_req, max_chunks=slot_count, raw=True).chunk():
                print("got chunk: ", chunk)
                if chunk['result_code'] == 0:
                    block = SignedBeaconBlock.decode_bytes(bytes.fromhex(chunk["data"]))
                    blocks.append(block)
                    current_slot = block.message.slot
                else:
                    print("failed to get block; msg: ", chunk["msg"])
                    break
            # TODO: could process blocks using as done with previous sync experiment. Just need to test RPC now though.

            return current_slot

        async def sync_work():
            current_slot = Slot(0)
            while True:
                current_slot = await sync_step(current_slot)
                if current_slot > 100:
                    break

        await sync_work()

        print("Saying goobye")
        ok_bye_bye = Goodbye(1)  # A.k.a "Client shut down"
        await morty.rpc.goodbye.req.raw(peer_id, ok_bye_bye.encode_bytes().hex(), raw=True)

        print("disconnecting")
        await morty.peer.disconnect(peer_id)
        print("disconnected")

    await sync_work()


async def run_work():
    async with SubprocessConn(cmd='cd ../rumor && go run . bare') as conn:
        # A Trio nursery hosts all the async tasks of the Rumor instance.
        async with trio.open_nursery() as nursery:
            # And optionally use Rumor(conn, debug=True) to be super verbose about Rumor communication.
            await sync_experiment(Rumor(conn, nursery))
            # Cancel the nursery to signal that we are not using Rumor anymore
            nursery.cancel_scope.cancel()

trio.run(run_work)
