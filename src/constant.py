# constants.py

# TODO:
# - world / character のキーをここに集約する
# - YAMLキーの一元管理
# - 将来的に relationships → character_relationships に変更予定
class MemoryKeys:
    FILE_STATUS = "file_status"
    CURRENT_STATE = "current_state"
    MEMORY = "memory"

class CurrentStateKeys:
    LOCATION = "location"
    STATUS = "status"
    ACTION = "action"
    OUTFIT = "outfit"
    MOOD = "mood"
    PARTICIPANTS = "participants"
    FOCUS_TARGETS = "focus_targets"

class MemoryDetailKeys:
    HISTORY = "history"
    PROGRESS = "progress"
    WORRIES = "worries"
    RELATIONSHIPS = "relationships"