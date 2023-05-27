files = [
    {
        "path": "settings.json",
        "content": """{{
  "title": "{title}",
  "source": "{source}",
  "limits": {{
    "TimeLimit": 1000,
    "MemoryLimit": 134217728,
    "InputLimit": 67108864,
    "OutputLimit": 67108864,
    "ExtraWallTime": 0,
    "OverallWallTimeLimit": 60000
  }},
  "validator": {{
    "name": "token-caseless",
    "limits": {{
      "TimeLimit": 1000
    }}
  }},
  "misc": {{
    "alias": "dummy-ofmi",
    "visibility": "private",
    "languages": "all",
    "email_clarifications": 0,
    "admin-groups": ["ofmi-2023"]
  }}
}}
""",
    },
]