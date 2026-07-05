def is_invalid_world_memory(data):
    return (
        not data
        or "現在の状態" not in data
        or "世界の状態" not in data
    )