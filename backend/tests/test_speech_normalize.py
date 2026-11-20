"""Tests for speech_normalize() — 40+ cases covering all transformation rules."""

from __future__ import annotations

import pytest
from app.utils.speech import speech_normalize


class TestUnits:
    """Physical unit expansion."""

    def test_metres_per_second(self):
        assert "metres per second" in speech_normalize("5 m/s")

    def test_kilometres_per_hour(self):
        assert "kilometres per hour" in speech_normalize("100 km/h")

    def test_metres_per_second_squared(self):
        result = speech_normalize("9.8 m/s²")
        assert "metres per second squared" in result

    def test_degrees_celsius(self):
        assert "degrees Celsius" in speech_normalize("20 °C")

    def test_degrees_fahrenheit(self):
        assert "degrees Fahrenheit" in speech_normalize("98.6 °F")

    def test_kilograms(self):
        assert "kilograms" in speech_normalize("70 kg")

    def test_grams(self):
        assert "grams" in speech_normalize("50 g")

    def test_milligrams(self):
        assert "milligrams" in speech_normalize("500 mg")

    def test_newtons(self):
        assert "newtons" in speech_normalize("10 N")

    def test_joules(self):
        assert "joules" in speech_normalize("100 J")

    def test_pascals(self):
        assert "pascals" in speech_normalize("101325 Pa")

    def test_kilopascals(self):
        assert "kilopascals" in speech_normalize("101.3 kPa")

    def test_watts(self):
        assert "watts" in speech_normalize("60 W")

    def test_kilowatts(self):
        assert "kilowatts" in speech_normalize("3.5 kW")

    def test_volts(self):
        assert "volts" in speech_normalize("230 V")

    def test_amps(self):
        assert "amps" in speech_normalize("15 A")

    def test_ohms(self):
        assert "ohms" in speech_normalize("1000 Ω")

    def test_hertz(self):
        assert "hertz" in speech_normalize("50 Hz")

    def test_megahertz(self):
        assert "megahertz" in speech_normalize("2.4 MHz")

    def test_litres(self):
        assert "litres" in speech_normalize("2 L")

    def test_millilitres(self):
        assert "millilitres" in speech_normalize("250 mL")

    def test_moles(self):
        assert "moles" in speech_normalize("0.5 mol")

    def test_metres(self):
        assert "metres" in speech_normalize("The distance is 10 m")


class TestSuperscriptsSubscripts:
    """Unicode superscript / subscript expansion."""

    def test_x_squared(self):
        result = speech_normalize("x²")
        assert "squared" in result

    def test_x_cubed(self):
        result = speech_normalize("v³")
        assert "cubed" in result

    def test_subscript_digits(self):
        # H₂O → H 2 O
        result = speech_normalize("H₂O")
        assert "2" in result

    def test_co2_subscript(self):
        result = speech_normalize("CO₂")
        assert "2" in result


class TestGreekLetters:
    """Greek letter expansion."""

    def test_alpha(self):
        assert "alpha" in speech_normalize("α particles")

    def test_beta(self):
        assert "beta" in speech_normalize("β decay")

    def test_gamma(self):
        assert "gamma" in speech_normalize("γ radiation")

    def test_delta(self):
        assert "delta" in speech_normalize("ΔT").lower()

    def test_pi(self):
        assert "pi" in speech_normalize("π r²")

    def test_omega(self):
        assert "omega" in speech_normalize("ω = 2πf")

    def test_lambda(self):
        assert "lambda" in speech_normalize("λ = 500 nm")

    def test_sigma(self):
        assert "sigma" in speech_normalize("σ = 5.67×10⁻⁸")

    def test_theta(self):
        assert "theta" in speech_normalize("angle θ")


class TestOperators:
    """Mathematical operator expansion."""

    def test_times(self):
        assert "times" in speech_normalize("3 × 4")

    def test_divided_by(self):
        assert "divided by" in speech_normalize("10 ÷ 2")

    def test_plus_or_minus(self):
        assert "plus or minus" in speech_normalize("5 ± 0.1")

    def test_not_equal(self):
        assert "not equal" in speech_normalize("a ≠ b")

    def test_less_than_or_equal(self):
        assert "less than or equal" in speech_normalize("x ≤ 10")

    def test_greater_than_or_equal(self):
        assert "greater than or equal" in speech_normalize("y ≥ 5")


class TestPercentage:
    """Percentage expansion."""

    def test_simple_percent(self):
        assert "percent" in speech_normalize("75%")

    def test_decimal_percent(self):
        assert "percent" in speech_normalize("12.5%")

    def test_space_before_percent(self):
        assert "percent" in speech_normalize("80 %")


class TestFigureReferences:
    """Figure / table reference expansion."""

    def test_fig_dot(self):
        result = speech_normalize("See Fig. 2.1 for details")
        assert "Figure" in result
        assert "point" in result

    def test_figure_full(self):
        result = speech_normalize("Figure 3 shows the graph")
        assert "Figure 3" in result

    def test_table_ref(self):
        result = speech_normalize("as shown in Table 1.2")
        assert "Table" in result
        assert "point" in result


class TestAbbreviations:
    """Latin abbreviation expansion."""

    def test_eg(self):
        result = speech_normalize("e.g. sodium")
        assert "for example" in result.lower()

    def test_ie(self):
        result = speech_normalize("i.e. 5 m/s")
        assert "that is" in result.lower()


class TestNoSideEffects:
    """Ensure clean text passes through without corruption."""

    def test_plain_english(self):
        text = "The cat sat on the mat."
        result = speech_normalize(text)
        assert "cat" in result
        assert "mat" in result

    def test_empty_string(self):
        assert speech_normalize("") == ""

    def test_multiline_preserved(self):
        text = "Line one.\nLine two."
        result = speech_normalize(text)
        assert "\n" in result

