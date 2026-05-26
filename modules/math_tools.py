import sympy as sp


def solve_math(expr: str):
    try:
        x = sp.symbols("x")
        if "=" in expr:
            left, right = expr.split("=", 1)
            sol = sp.solve(sp.sympify(left) - sp.sympify(right), x)
            return f"### Solution\n`{expr}`\n\n**x = {sol}**"
        result = sp.sympify(expr)
        simplified = sp.simplify(result)
        return f"### Result\n`{expr}`\n\n**{simplified}**"
    except Exception as e:
        return f"Could not solve that expression. Error: {e}"


def formula_sheet(topic: str):
    topic = topic.lower()
    if "earth pressure" in topic:
        return """### Common Earth Pressure Formula Sheet

- At-rest earth pressure: `K0 = 1 - sin(phi)` for normally consolidated soil
- Active Rankine coefficient: `Ka = tan^2(45° - phi/2)`
- Passive Rankine coefficient: `Kp = tan^2(45° + phi/2)`
- Active lateral pressure: `sigma_h = Ka * gamma * z`
- Passive lateral pressure: `sigma_h = Kp * gamma * z`
- Resultant triangular force: `P = 0.5 * K * gamma * H^2`
- With surcharge: `sigma_q = K * q`
"""
    return "No local formula sheet for this topic yet. Use the Research Chat for internet-based formulas."
