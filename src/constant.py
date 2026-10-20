# constants.py

# TODO:
# - world / character のキーをここに集約する
# - YAMLキーの一元管理
# - 将来的に relationships → character_relationships に変更予定
class Bootstrap:
    MEMORY_MIDDLE_SUMMARY = "00_query_create_character_memory_middle_summary.yaml"
    MEMORY_MIDDLE_CATEGORIZE = "00_query_create_character_memory_middle_categorize.yaml"
    MEMORY_MIDDLE_LOCATION = "00_query_create_character_memory_middle_location.yaml"
    MEMORY_MIDDLE_CLOTHING = "00_query_create_character_memory_middle_clothing.yaml"
    MEMORY_MIDDLE_ITEMS = "00_query_create_character_memory_middle_items.yaml"
    MEMORY_MIDDLE_TARGET = "00_query_create_character_memory_middle_target.yaml"
    MEMORY_MIDDLE_CURRENCY = "00_query_create_character_memory_middle_currency.yaml"
    EDIT_SUMMARY         = "01_query_create_edit_summary.yaml"
    WORLD_MEMORY         = "01_query_create_world_memory.yaml"
    SUB_CHARACTER_TEMPLATE = "sub_character.yaml"
      
class PromptsPreprocess:
    WORLD_MEMORY          = "01_query_update_world_memory.yaml"
    PLAYER_IDENTIFICATION = "99_query_judge_player_identification.yaml"

class PromptsMain:
    VALIDATION_CHAT          = "01_query_validation_chat.yaml"
    CHAT                     = "02_query_chat.yaml"
    CHARACTER_IDENTIFICATION = "02_query_judge_character_identification.yaml"
    ATTENTION                = "03_query_judge_attention.yaml"
    CROSS_TALK               = "04_query_cross_talk.yaml"
    NEWCOMER                 = "00_query_judge_newcomer.yaml"

class PromptsPostprocess:
    EDIT_SUMMARY          = "01_query_update_edit_summary.yaml"
    PARAMETER_FLUCTUATION = "01_query_parameter_fluctuation.yaml"
    WORLD_MEMORY          = "01_query_update_world_memory.yaml"
    CHARACTER_ITEMS       = "02_query_update_character_items.yaml"
    CHARACTER_MEMORY      = "02_query_update_character_memory.yaml"
