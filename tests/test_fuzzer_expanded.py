import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.core.fuzzer import ProtocolFuzzer

@pytest.mark.asyncio
async def test_expanded_fuzzer_strategies_and_seed():
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node.yaml")
    assert spec is not None

    fuzzer1 = ProtocolFuzzer(spec, seed=42)
    fuzzer2 = ProtocolFuzzer(spec, seed=42)

    vecs1 = fuzzer1.select_vectors(20)
    vecs2 = fuzzer2.select_vectors(20)

    assert len(vecs1) == len(vecs2)
    assert [v.strategy for v in vecs1] == [v.strategy for v in vecs2]
    assert [v.raw_payload for v in vecs1] == [v.raw_payload for v in vecs2]

    # Run campaign
    report = await fuzzer1.run_campaign(max_vectors=10)
    assert report.total_vectors > 0
    assert report.seed == 42
