# Lessons Learned - MCP GESAD

Este archivo documenta patrones de errores, correcciones aplicadas, y reglas para prevenir errores futuros, siguiendo el "Self-Improvement Loop" de CLAUDE.md.

---

## 2026-02-22: Primera Revisión y Correcciones Aplicadas

### Lección 1: Infraestructura de Workflow es Fundamental

**Contexto:**
- El proyecto no tenía directorio `tasks/` ni archivos de tracking
- Violaba las reglas de CLAUDE.md sobre task management

**Problema:**
- Sin tracking de tareas, planes, o lecciones aprendidas
- Dificulta colaboración y continuidad entre sesiones

**Solución Aplicada:**
- Crear estructura `tasks/` con archivos requeridos
- Establecer templates para futuras tareas

**Regla para el Futuro:**
> **SIEMPRE** crear infraestructura de workflow (`tasks/todo.md`, `tasks/lessons.md`) al inicio de cualquier proyecto nuevo. No esperar a que falte.

---

### Lección 2: Typos en Default Values Son Peligrosos

**Contexto:**
- `config.py:164` tenía `"defalse"` en lugar de `"false"`
- Afecta comportamiento por defecto de webhooks

**Problema:**
- Los typos en default values pueden causar bugs silenciosos
- No detectables por linters estándar (es un string válido)

**Solución Aplicada:**
- Corregir typo inmediatamente
- Agregar validación en tests

**Regla para el Futuro:**
> **VALIDAR** default values con tests unitarios. Para booleans, testear explícitamente los casos: env var ausente, "true", "false", valores inválidos.

**Ejemplo de Test:**
```python
def test_webhook_enabled_default():
    # Sin env var definida
    assert Config.WEBHOOK_ENABLED == False

def test_webhook_enabled_true():
    os.environ['GESAD_WEBHOOK_ENABLED'] = 'true'
    assert Config.WEBHOOK_ENABLED == True
```

---

### Lección 3: Código Comentado/Muerto Reduce Calidad

**Contexto:**
- `data_processor.py:75-98` contenía diccionario de trabajadores de ejemplo nunca usado
- 24 líneas que aumentan complejidad sin valor

**Problema:**
- Código muerto confunde a nuevos desarrolladores
- Incrementa superficie de mantenimiento
- Viola principio "Minimal Impact" de CLAUDE.md

**Solución Aplicada:**
- Eliminar completamente (no comentar)
- Si es útil para demos, mover a `scripts/demo.py`

**Regla para el Futuro:**
> **NUNCA** dejar código comentado o no usado en producción. Si es valioso:
> - Moverlo a tests/ejemplos
> - Documentarlo en docs/
> - O eliminarlo completamente
>
> Git mantiene el historial, no necesitas comentarios.

---

### Lección 4: Simplicidad es Rey

**Contexto:**
- El proyecto demuestra excelente simplicidad en arquitectura
- Funciones con propósito único, sin abstracciones prematuras

**Qué Funcionó Bien:**
- Configuración centralizada en `config.py`
- Separación clara: cada módulo tiene una responsabilidad
- Cache implementado solo cuando es necesario (no prematuro)

**Regla para Reforzar:**
> **ANTES** de agregar abstracción, preguntar:
> - ¿Es realmente necesaria ahora?
> - ¿Hay 3+ casos de uso concretos?
> - ¿Simplifica o complica?
>
> Si dudas, NO abstraer. YAGNI (You Ain't Gonna Need It).

---

### Lección 5: Investigar Antes de Eliminar Código

**Contexto:**
- Durante las correcciones, eliminé código muerto en `data_processor.py:75-98`
- El código estaba después de un `return`, por lo que era inalcanzable
- Pero luego descubrí que otra función intentaba usar `self.trabajadores_ejemplo`

**Problema:**
- Eliminé código pensando que era totalmente muerto
- Pero había una referencia a ese atributo en otro método (línea 373)
- El bug original era que el atributo NUNCA se inicializaba (código inalcanzable)

**Solución Aplicada:**
- Investigué todas las referencias a `trabajadores_ejemplo` con Grep
- Entendí que el código tenía un bug latente (variable nunca inicializada)
- Moví la inicialización al lugar correcto (`__init__`)
- Eliminé el código inalcanzable

**Regla para el Futuro:**
> **ANTES** de eliminar código, usar Grep para buscar TODAS las referencias:
> ```bash
> grep -r "nombre_variable" .
> ```
> Si encuentras referencias:
> 1. Investiga si son activas o también código muerto
> 2. Si son activas, determina si hay un bug (como variable no inicializada)
> 3. Corrige la causa raíz, no solo elimines

**Ejemplo Correcto:**
```python
# MAL: Código inalcanzable
def metodo(self):
    return algo
    self.variable = valor  # NUNCA se ejecuta

# BIEN: Inicializar en __init__
def __init__(self):
    self.variable = valor
```

---

### Lección 6: Verificar Correcciones con el Sistema Completo

**Contexto:**
- Después de aplicar correcciones, ejecuté tests unitarios
- Muchos tests fallaron, pero NO por mis correcciones
- Era importante distinguir fallos pre-existentes de nuevos fallos

**Qué Funcionó Bien:**
- Validé importando cada módulo individualmente
- Verifiqué que los valores corregidos fueran correctos
- Probé la inicialización del sistema completo
- Usé prints para confirmar estado esperado

**Regla para Reforzar:**
> **DESPUÉS** de correcciones, verificar en orden:
> 1. **Sintaxis:** Módulo importa sin errores
> 2. **Valores:** Variables tienen valores esperados
> 3. **Integración:** Sistema completo inicializa
> 4. **Tests:** Ejecutar tests (distinguir pre-existentes vs nuevos fallos)
>
> No confiar solo en tests - pueden estar desactualizados

**Comandos útiles:**
```bash
# 1. Verificar import
python -c "from modulo import clase"

# 2. Verificar valores
python -c "from modulo import var; print(var)"

# 3. Verificar sistema
python -c "import todos; los; modulos; print('OK')"
```

---

## Template para Nuevas Lecciones

```markdown
## [Fecha]: [Título de la Lección]

### Contexto:
[Qué estabas haciendo cuando ocurrió el error/aprendizaje]

### Problema:
[Qué salió mal o qué patrón negativo se identificó]

### Solución Aplicada:
[Cómo se corrigió]

### Regla para el Futuro:
> [Regla específica y accionable para prevenir repetición]

### Ejemplo (opcional):
```python
# Código correcto
```
```

---

## Patrones a Evitar (Consolidado)

1. ❌ Proyecto sin `tasks/` desde el inicio
2. ❌ Typos en default values sin tests
3. ❌ Código muerto/comentado en producción
4. ❌ Abstracciones prematuras
5. ❌ Configuración hardcodeada (usar env vars)

## Patrones a Seguir (Consolidado)

1. ✅ Configuración centralizada con defaults sensatos
2. ✅ Logging comprehensivo con niveles apropiados
3. ✅ Type hints en todas las funciones públicas
4. ✅ Tests para casos edge (timezone, TTL, etc.)
5. ✅ Async/await para I/O operations
6. ✅ Documentación en markdown + docstrings
7. ✅ Separación de concerns (un módulo = una responsabilidad)

---

**Nota:** Este archivo debe actualizarse **INMEDIATAMENTE** después de cada corrección del usuario. Es tu memoria a largo plazo para mejorar continuamente.
