import asyncio

from app.websocket_manager import ClientSlot, OutboundBuffer


def upd(i):
    return {"type": "gesture", "phase": "update", "seq": i}


def test_slot_single_owner():
    slot, a, b = ClientSlot(), object(), object()
    assert slot.try_acquire(a)
    assert not slot.try_acquire(b)
    slot.release(b)  # non-owner release is ignored
    assert slot.occupied
    slot.release(a)
    assert slot.try_acquire(b)


def test_buffer_drops_stale_updates_but_keeps_transitions():
    async def go():
        buf = OutboundBuffer(max_pending=3)
        buf.push({"type": "gesture", "phase": "start", "seq": 0})
        for i in range(1, 6):
            buf.push(upd(i))
        buf.push({"type": "gesture", "phase": "end", "seq": 9})
        batch = await buf.get_batch()
        phases = [m["phase"] for m in batch]
        assert phases[0] == "start" and phases[-1] == "end"
        assert upd(5) in batch and upd(1) not in batch

    asyncio.run(go())
