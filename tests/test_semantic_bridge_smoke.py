def test_semantic_bridge_import() -> None:
    import harness.semantic_bridge as semantic_bridge

    assert hasattr(semantic_bridge, "evaluate_semantic_gate")
