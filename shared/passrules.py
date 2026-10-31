"""Reglas de la contraseña de una cuenta (las comparten el cliente, que avisa al escribir, y el servidor, que las exige)."""
MIN_LEN, MAX_LEN = 8, 64


def problem(password):
    """Motivo por el que una contraseña no vale (None si es valida)."""
    if not isinstance(password, str):
        return "Contraseña invalida"
    if len(password) < MIN_LEN:
        return f"La contraseña debe tener al menos {MIN_LEN} caracteres"
    if len(password) > MAX_LEN:
        return f"La contraseña admite como máximo {MAX_LEN} caracteres"
    return None
