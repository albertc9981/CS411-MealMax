from contextlib import contextmanager
import re
import sqlite3

import pytest

from meal_max.models.kitchen_model import (
    Meal,
    create_meal,
    clear_meals,
    delete_meal,
    get_leaderboard,
    get_meal_by_id,
    get_meal_by_name,
    update_meal_stats
)

def normalize_whitespace(sql_query: str) -> str:
    return re.sub(r'\s+', ' ', sql_query).strip()

@pytest.fixture
def mock_cursor(mocker):
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()

    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  
    mock_cursor.fetchall.return_value = []
    mock_conn.commit.return_value = None

    @contextmanager
    def mock_get_db_connection():
        yield mock_conn  

    mocker.patch("meal_max.models.kitchen_model.get_db_connection", mock_get_db_connection)

    return mock_cursor 

def test_create_meal(mock_cursor):
    """Test that creating a meal executes the correct SQL insert statement."""
    meal_data = {
        "meal": "Butter Chicken",
        "cuisine": "Indian",
        "price": 14.75,
        "difficulty": "MED"
    }
    
    create_meal(**meal_data)

    expected_query = """
        INSERT INTO meals (meal, cuisine, price, difficulty)
        VALUES (?, ?, ?, ?)
    """
    normalized_expected_query = normalize_whitespace(expected_query)
    actual_query, actual_params = mock_cursor.execute.call_args[0]
    normalized_actual_query = normalize_whitespace(actual_query)
    
    assert normalized_actual_query == normalized_expected_query
    assert actual_params == (
        meal_data["meal"],
        meal_data["cuisine"],
        meal_data["price"],
        meal_data["difficulty"],
    )

def test_create_meal_negative_price():
    """Test creating a meal with a negative price raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid price: .* Price must be a positive number."):
        create_meal("Fries", "American", -3.5, "LOW")

def test_create_meal_invalid_difficulty():
    """Test creating meal with invalid difficulty level."""
    with pytest.raises(ValueError, match="Invalid difficulty level: .* Must be 'LOW', 'MED', or 'HIGH'."):
        create_meal("Carbonara", "Italian", 12.99, "EASY")

def test_create_meal_duplicate(mock_cursor):
    """Test creating a meal with an existing name."""
    mock_cursor.execute.side_effect = sqlite3.IntegrityError
    with pytest.raises(ValueError, match="Meal with name 'Miso Ramen' already exists"):
        create_meal("Miso Ramen", "Japanese", 13.4, "LOW")

def test_clear_meals(mock_cursor, mocker):
    """Test clearing all meals."""
    mocker.patch.dict("os.environ", {"SQL_CREATE_TABLE_PATH": "sql/create_meal_table.sql"})
    mock_open = mocker.patch("builtins.open", mocker.mock_open(read_data="SQL_CREATE_TABLE"))

    clear_meals()

    mock_open.assert_called_once_with("sql/create_meal_table.sql", "r")

    mock_cursor.executescript.assert_called_once_with("SQL_CREATE_TABLE")

def test_delete_meal_marks_as_deleted(mock_cursor):
    """Test deleting a meal correctly updates deleted status in the database."""
    mock_cursor.fetchone.return_value = (False,)

    delete_meal(1)

    expected_select_query = normalize_whitespace("SELECT deleted FROM meals WHERE id = ?")
    expected_update_query = normalize_whitespace("UPDATE meals SET deleted = TRUE WHERE id = ?")

    mock_cursor.execute.assert_any_call(expected_select_query, (1,))
    mock_cursor.execute.assert_any_call(expected_update_query, (1,))
    assert mock_cursor.execute.call_count == 2

def test_delete_meal_already_deleted(mock_cursor):
    """Test deleting an already deleted meal."""
    mock_cursor.fetchone.return_value = (True,)
    
    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        delete_meal(1)
    
    expected_select_query = normalize_whitespace("SELECT deleted FROM meals WHERE id = ?")
    mock_cursor.execute.assert_called_once_with(expected_select_query, (1,))

def test_delete_meal_not_found(mock_cursor):
    """Test deleting a meal that does not exist."""
    mock_cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="Meal with ID 1 not found"):
        delete_meal(1)

def test_get_leaderboard_sorted(mock_cursor):
    """Test getting leaderboard sorted by wins and win percentage."""
    
    # Test sorting by wins
    mock_cursor.fetchall.return_value = [
        (1, "Butter Chicken", "Indian", 14.75, "MED", 10, 7, 0.7)
    ]
    leaderboard_by_wins = get_leaderboard("wins")
    assert leaderboard_by_wins[0]["meal"] == "Butter Chicken"
    
    # Test sorting by win percentage
    mock_cursor.fetchall.return_value = [
        (3, "Burger", "American", 8.99, "MED", 5, 4, 0.8),     
        (2, "Pizza", "Italian", 10.99, "LOW", 8, 6, 0.75),      
        (1, "Spaghetti", "Italian", 12.99, "MED", 10, 7, 0.7)   
    ]
    leaderboard_by_win_pct = get_leaderboard("win_pct")
    assert leaderboard_by_win_pct[0]["meal"] == "Burger"
    assert leaderboard_by_win_pct[1]["meal"] == "Pizza"
    assert leaderboard_by_win_pct[2]["meal"] == "Spaghetti"

def test_get_leaderboard_invalid_sort_by():
    """Test getting leaderboard with invalid sorting."""
    with pytest.raises(ValueError, match="Invalid sort_by parameter: unknown"):
        get_leaderboard("unknown")

def test_get_meal_by_id(mock_cursor):
    """Test successfully getting meal by ID."""
    
    mock_cursor.fetchone.return_value = (1, "Mac 'n Cheese", "American", 8.99, "LOW", False)

    meal = get_meal_by_id(1)
    expected_result = Meal(id=1, meal="Mac 'n Cheese", cuisine="American", price=8.99, difficulty="LOW")

    assert meal == expected_result, f"Expected {expected_result}, got {meal}"

    expected_query = normalize_whitespace(
        "SELECT id, meal, cuisine, price, difficulty, deleted FROM meals WHERE id = ?"
    )
    actual_query = normalize_whitespace(mock_cursor.execute.call_args[0][0])

    assert actual_query == expected_query, "The SQL query did not match the expected structure."

    actual_arguments = mock_cursor.execute.call_args[0][1]
    expected_arguments = (1,)

    assert actual_arguments == expected_arguments, f"The SQL query arguments did not match. Expected {expected_arguments}, got {actual_arguments}."

def test_get_meal_by_bad_id(mock_cursor):
    """Test getting meal by a non-existent ID."""
    mock_cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="Meal with ID 1 not found"):
        get_meal_by_id(1)

def test_get_meal_by_name(mock_cursor):
    """Test successfully getting meal by name."""
    mock_cursor.fetchone.return_value = (1, "Mac 'n Cheese", "American", 8.99, "LOW", False)
    meal = get_meal_by_name("Mac 'n Cheese")
    assert meal.cuisine == "American"

def test_get_meal_by_non_existent_name(mock_cursor):
    """Test getting meal by name when not found."""
    mock_cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="Meal with name Mac 'n Cheese not found"):
        get_meal_by_name("Mac 'n Cheese")

def test_update_meal_stats_win(mock_cursor):
    """Test updating meal stats with a win."""
    
    mock_cursor.fetchone.return_value = (False,)  # Indicates meal is not deleted

    meal_id = 1
    update_meal_stats(meal_id, "win")

    expected_select_query = normalize_whitespace("SELECT deleted FROM meals WHERE id = ?")
    actual_select_query = normalize_whitespace(mock_cursor.execute.call_args_list[0][0][0])
    assert actual_select_query == expected_select_query, "The SELECT query did not match the expected structure."

    expected_select_arguments = (meal_id,)
    actual_select_arguments = mock_cursor.execute.call_args_list[0][0][1]
    assert actual_select_arguments == expected_select_arguments, f"The SELECT query arguments did not match. Expected {expected_select_arguments}, got {actual_select_arguments}."

    expected_update_query = normalize_whitespace("UPDATE meals SET battles = battles + 1, wins = wins + 1 WHERE id = ?")
    actual_update_query = normalize_whitespace(mock_cursor.execute.call_args_list[1][0][0])
    assert actual_update_query == expected_update_query, "The UPDATE query did not match the expected structure."

    expected_update_arguments = (meal_id,)
    actual_update_arguments = mock_cursor.execute.call_args_list[1][0][1]
    assert actual_update_arguments == expected_update_arguments, f"The UPDATE query arguments did not match. Expected {expected_update_arguments}, got {actual_update_arguments}."

    assert mock_cursor.execute.call_count == 2, f"Expected 2 SQL calls (SELECT and UPDATE), but got {mock_cursor.execute.call_count}."

def test_update_meal_stats_loss(mock_cursor):
    """Test updating meal stats with a loss."""
    
    mock_cursor.fetchone.return_value = (False,)  # Meal is not marked as deleted

    meal_id = 1
    update_meal_stats(meal_id, "loss")

    expected_select_query = normalize_whitespace("SELECT deleted FROM meals WHERE id = ?")
    actual_select_query = normalize_whitespace(mock_cursor.execute.call_args_list[0][0][0])
    assert actual_select_query == expected_select_query, "The SELECT query did not match the expected structure."

    expected_select_arguments = (meal_id,)
    actual_select_arguments = mock_cursor.execute.call_args_list[0][0][1]
    assert actual_select_arguments == expected_select_arguments, f"The SELECT query arguments did not match. Expected {expected_select_arguments}, got {actual_select_arguments}."

    expected_update_query = normalize_whitespace("UPDATE meals SET battles = battles + 1 WHERE id = ?")
    actual_update_query = normalize_whitespace(mock_cursor.execute.call_args_list[1][0][0])
    assert actual_update_query == expected_update_query, "The UPDATE query did not match the expected structure."

    expected_update_arguments = (meal_id,)
    actual_update_arguments = mock_cursor.execute.call_args_list[1][0][1]
    assert actual_update_arguments == expected_update_arguments, f"The UPDATE query arguments did not match. Expected {expected_update_arguments}, got {actual_update_arguments}."

    assert mock_cursor.execute.call_count == 2, f"Expected 2 SQL calls (SELECT and UPDATE), but got {mock_cursor.execute.call_count}."

def test_update_meal_stats_non_existent(mock_cursor):
    """Test updating meal stats for a non-existent meal."""
    mock_cursor.fetchone.return_value = None
    
    with pytest.raises(ValueError, match="Meal with ID 1 not found"):
        update_meal_stats(1, "win")
    
    mock_cursor.execute.assert_called_once_with("SELECT deleted FROM meals WHERE id = ?", (1,))

def test_update_meal_stats_deleted_meal(mock_cursor):
    """Test updating meal stats for a meal that has already been deleted."""
    mock_cursor.fetchone.return_value = (True,)
    
    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        update_meal_stats(1, "win")
    
    mock_cursor.execute.assert_called_once_with("SELECT deleted FROM meals WHERE id = ?", (1,))