from app.models import OfferLinkStatus, StreamOffer


def recalculate_weights(offers: list[StreamOffer]) -> None:
    """Redistribute weights among active (non-removed) offers; respect pinned weights."""
    active = [o for o in offers if o.status == OfferLinkStatus.active.value]
    if not active:
        return

    pinned = [o for o in active if o.weight_pinned]
    pinned_sum = sum(o.weight for o in pinned)
    free = [o for o in active if not o.weight_pinned]

    if not free:
        return

    remaining = max(0.0, 100.0 - pinned_sum)
    if remaining <= 0:
        for offer in free:
            offer.weight = 0.0
        return

    share = remaining / len(free)
    for offer in free:
        offer.weight = round(share, 4)