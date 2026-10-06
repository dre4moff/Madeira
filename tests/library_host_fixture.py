"""Production Swift definitions needed by saved-profile host fixtures."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolution_choices():
    source = (ROOT / 'app/Madeira/GuestDisplay.swift').read_text()
    start = source.index('enum ResolutionChoices {')
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def control_action():
    source = (ROOT / 'app/Madeira/ContentView.swift').read_text()
    return source[source.index('enum ControlAction:'):source.index('/// One on-screen control.')]
