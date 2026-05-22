from agents.guidance_extractor import extract_guidance_capex
from agents.segment_extractor import extract_segments


def test_extract_guidance_capex_range():
    text = (
        "For the next quarter, the company expects revenue guidance of $11.0 billion "
        "to $12.5 billion. Capital expenditures are expected to be approximately $4.2 billion "
        "for AI infrastructure."
    )
    g = extract_guidance_capex(text)
    assert g.next_q_revenue_low is not None
    assert g.next_q_revenue_high is not None
    assert g.capex_amount is not None


def test_extract_segments_data_center():
    text = "Data Center revenue was $22.6 billion, up from prior year."
    segs = extract_segments(text)
    assert len(segs) >= 1
    assert segs[0].revenue is not None
