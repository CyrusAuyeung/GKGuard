from app.vision.upper_color_postprocess import choose_upper_color_from_probs


def test_gray_with_close_stripe_probability_is_striped():
    color = choose_upper_color_from_probs(
        {
            "gray": 0.142,
            "striped": 0.135,
            "blue": 0.096,
            "black": 0.091,
        }
    )

    assert color == "striped"


def test_low_confidence_blue_cast_can_return_gray():
    color = choose_upper_color_from_probs(
        {
            "blue": 0.116,
            "purple": 0.115,
            "gray": 0.110,
            "black": 0.090,
            "white": 0.082,
        }
    )

    assert color == "gray"


def test_confident_blue_is_not_forced_to_neutral():
    color = choose_upper_color_from_probs(
        {
            "blue": 0.154,
            "purple": 0.094,
            "gray": 0.092,
            "white": 0.085,
        }
    )

    assert color == "blue"


def test_low_confidence_red_cast_can_return_black():
    color = choose_upper_color_from_probs(
        {
            "red": 0.110,
            "purple": 0.104,
            "black": 0.096,
            "gray": 0.087,
        }
    )

    assert color == "black"
