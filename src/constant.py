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

class Bootstrap:
    EDIT_SUMMARY         = "01_query_create_edit_summary.yaml"
    WORLD_MEMORY         = "01_query_create_world_memory.yaml"
    CHARACTER_ITEMS      = "02_query_create_character_items.yaml"
    CHARACTER_MEMORY     = "02_query_create_character_memory.yaml"
    SUB_CHARACTER_MEMORY = "03_query_create_sub_character_memory.yaml"
      
class PromptsPreprocess:
    EDIT_SUMMARY          = "01_query_update_edit_summary.yaml"
    WORLD_MEMORY          = "01_query_update_world_memory.yaml"
    PLAYER_IDENTIFYCATION = "99_query_judge_player_identification.yaml"

class PromptsMain:
    VALIDATION_CHAT          = "01_query_validation_chat.yaml"
    CHAT                     = "02_query_chat.yaml"
    CHARACTER_IDENTIFICATION = "02_query_judge_character_identification.yaml"

class PromptsPostprocess:
    PARAMETER_FLUCTUATION = "01_query_parameter_fluctuation.yaml"
    WORLD_MEMORY          = "01_query_update_world_memory.yaml"
    CHARACTER_ITEMS       = "02_query_update_character_items.yaml"
    CHARACTER_MEMORY      = "02_query_update_character_memory.yaml"