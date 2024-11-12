import pytest

from meal_max.models.battle_model import BattleModel
from meal_max.models.kitchen_model import Meal

@pytest.fixture()
def battle_model():
    """Fixture to provide a new instance of BattleModel for each test."""
    return BattleModel()

@pytest.fixture
def mock_update_meal_stats(mocker):
    """Mock the update_meal_stats function for testing purposes."""
    return mocker.patch("meal_max.models.battle_model.update_meal_stats")

"""Fixtures providing sample meals for the tests."""
@pytest.fixture
def sample_meal1():
    return Meal(1, "Spaghetti Bolognese", "Italian", 14.5, "MED")

@pytest.fixture
def sample_meal2():
    return Meal(2, "Bean Burrito", "Mexican", 9.75, "LOW")

@pytest.fixture
def sample_battle(sample_meal1, sample_meal2):
    return [sample_meal1, sample_meal2]

def test_prep_combatant(battle_model, sample_meal1, sample_meal2):
    """Test that combatants can be prepared and added to the battle."""
    battle_model.prep_combatant(sample_meal1)
    assert len(battle_model.get_combatants()) == 1
    assert battle_model.get_combatants()[0] == sample_meal1

    battle_model.prep_combatant(sample_meal2)
    assert len(battle_model.get_combatants()) == 2
    assert battle_model.get_combatants()[1] == sample_meal2

    with pytest.raises(ValueError, match="Combatant list is full"):
        battle_model.prep_combatant(sample_meal1)

##################################################
# Get Combatant/Score Test Cases
##################################################

def test_get_combatants(battle_model, sample_meal1, sample_meal2):
    """Test the correct list of combatants are returned after prep."""
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)
    combatants = battle_model.get_combatants()
    assert len(combatants) == 2
    assert combatants[0] == sample_meal1
    assert combatants[1] == sample_meal2

def test_get_combatants_empty_combatants(battle_model):
    """Test an empty list is returned when no combatants are prepped."""
    assert len(battle_model.get_combatants()) == 0

def test_get_battle_score(battle_model, sample_meal1):
    """Test that the battle score is calculated correctly based on meal attributes."""
    score = battle_model.get_battle_score(sample_meal1)
    expected_score = (sample_meal1.price * len(sample_meal1.cuisine)) - 2
    assert score == expected_score

def test_get_battle_score_invalid_difficulty(battle_model):
    """Test that an error is raised with an unexpected difficulty level."""
    with pytest.raises(ValueError, match="Difficulty must be 'LOW', 'MED', or 'HIGH'"):
        invalid_meal = Meal(3, "Invalid Meal", "Japanese", 12.0, "EXTREME")

##################################################
# Clear Combatant/Score Test Cases
##################################################

def test_clear_combatants(battle_model, sample_meal1, sample_meal2):
    """Test that combatants can be cleared from the battle."""
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)
    assert len(battle_model.get_combatants()) == 2

    battle_model.clear_combatants()
    assert len(battle_model.get_combatants()) == 0

def test_clear_combatants_empty_combatants(battle_model):
    """Test clearing combatants when there are no combatants."""
    assert len(battle_model.get_combatants()) == 0

    battle_model.clear_combatants()
    assert len(battle_model.get_combatants()) == 0

def test_battle_with_two_combatants(battle_model, sample_meal1, sample_meal2, mocker):
    """Test that a battle can occur with two prepared combatants and that stats are updated."""
    mock_random = mocker.patch("meal_max.models.battle_model.get_random", return_value=0.3)  # Adjust based on expected delta
    mock_update_meal_stats = mocker.patch("meal_max.models.battle_model.update_meal_stats")
    
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)
    
    winner = battle_model.battle()
    assert winner in [sample_meal1.meal, sample_meal2.meal]
    assert len(battle_model.get_combatants()) == 1  # Only one combatant remains

    if winner == sample_meal1.meal:
        mock_update_meal_stats.assert_any_call(sample_meal1.id, "win")
        mock_update_meal_stats.assert_any_call(sample_meal2.id, "loss")
    else:
        mock_update_meal_stats.assert_any_call(sample_meal2.id, "win")
        mock_update_meal_stats.assert_any_call(sample_meal1.id, "loss")

def test_battle_with_less_combatants(battle_model):
    """Test that starting a battle with fewer than two combatants raises an error."""
    with pytest.raises(ValueError, match="Two combatants must be prepped for a battle"):
        battle_model.battle()

def test_random_outcome(battle_model, sample_meal1, sample_meal2, mock_update_meal_stats, mocker):
    """Test that changing the random number can change the outcome of the battle."""
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)

    mocker.patch("meal_max.models.battle_model.get_random", return_value=0.1)
    winner_first = battle_model.battle()
    high_score_meal = sample_meal1 if battle_model.get_battle_score(sample_meal1) > battle_model.get_battle_score(sample_meal2) else sample_meal2
    assert winner_first == high_score_meal.meal

    battle_model.clear_combatants()
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)

    mocker.patch("meal_max.models.battle_model.get_random", return_value=0.9)
    winner_second = battle_model.battle()
    low_score_meal = sample_meal1 if high_score_meal != sample_meal1 else sample_meal2
    assert winner_second == low_score_meal.meal