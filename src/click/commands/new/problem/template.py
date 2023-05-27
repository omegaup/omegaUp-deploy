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
    {
        "path": "statements/es.markdown",
        "content": """_insertar descripción del problema aquí_

# Entrada

_inserta descripción de la entrada aquí_

# Salida

_inserta descripción de la salida aquí_

# Ejemplo

||examplefile
{sample}
||description
_insertar descripción del ejemplo aquí_
||end

# Límites

- _inserta límites de las variables aquí_

# Subtareas

- Subtarea _inserta número aquí_ (_insertar puntos aquí_ puntos): _inserta descripción aquí_

"""  # noqa,
    },
    {
        "path": "cases/{sample}.in",
        "content": "",
    },
    {
        "path": "cases/{sample}.out",
        "content": "",
    },
    {
        "path": "tests/tests.json",
        "content": """{{
  "max_score": 100
}}""",
    },
    {
        "path": "testplan",
        "content": "{sample} 100\n",
    }
]

symlinks = [
    {
        "src": "cases/{sample}.in",
        "dst": "examples/{sample}.in",
    },
    {
        "src": "cases/{sample}.out",
        "dst": "examples/{sample}.out",
    }
]
