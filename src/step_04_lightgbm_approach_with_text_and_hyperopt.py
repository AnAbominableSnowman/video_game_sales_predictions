from __future__ import annotations
import lightgbm as lgb
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split

from numpy import ndarray
import os
from hyperopt import hp, fmin, tpe
import pickle
import json
from pathlib import Path


def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    cars = pd.read_parquet(filepath)
    categorical_columns = cars.select_dtypes(include=["object"]).columns.tolist()
    existing_categorical_columns = [
        col for col in categorical_columns if col in cars.columns
    ]
    if existing_categorical_columns:
        cars[existing_categorical_columns] = cars[existing_categorical_columns].astype(
            "category"
        )
    return cars


def split_data(cars: pd.DataFrame, target_column: str):
    y = cars.pop(target_column).to_numpy()
    X_train, X_test, y_train, y_test = train_test_split(
        cars, y, test_size=0.2, random_state=2018
    )
    return X_train, X_test, y_train, y_test


def train_lightgbm(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: ndarray,
    y_test: ndarray,
    params: dict,
):
    categorical_columns = X_train.select_dtypes(include=["category"]).columns.tolist()

    train_data = lgb.Dataset(
        X_train, label=y_train, categorical_feature=categorical_columns
    )
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    evals_result = {}

    model = lgb.train(
        params,
        train_data,
        num_boost_round=5_000,
        valid_sets=[train_data, test_data],
        valid_names=["training", "validation"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=10, min_delta=10.0),
            lgb.record_evaluation(evals_result),
        ],
    )

    y_pred = model.predict(X_test, num_iteration=model.best_iteration)
    return model, y_pred, evals_result


def evaluate_model(y_test, y_pred, model_path):
    rmse = root_mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"Root Mean Squared Error (RMSE): {rmse}")
    print(f"R-squared (R2): {r2}")
    # Save results to a JSON file
    results = {"RMSE": rmse, "R-squared": r2}
    # Define the model path
    # Define the model path
    model_path = Path(model_path)  # Update with your actual path

    # Create the directory if it does not exist
    model_path.mkdir(parents=True, exist_ok=True)

    # Save results to JSON file
    with open(model_path / "evaluation_results.json", "w") as json_file:
        json.dump(results, json_file)
    return rmse, r2


def plot_results(y_test, y_pred, save_path):
    residuals = y_test - y_pred
    plt.scatter(y_pred, residuals, edgecolor="k", alpha=0.4)
    plt.axhline(y=0, color="r", linestyle="--", lw=2)
    plt.xlabel("Predicted")
    plt.ylabel("Residuals")
    plt.title("Residuals Plot")

    plt.tight_layout()
    directory = os.path.dirname(f"{save_path}")
    if not os.path.exists(directory):
        os.makedirs(directory)
    plt.savefig(f"{save_path}predicted_vs_actual.png")
    plt.close()


def objective(params, cars, target_column):
    selected_features = [col for col in cars.columns if col != target_column]

    X = cars[selected_features]
    y = cars[target_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=2018
    )

    # Set the parameters for LightGBM
    lightgbm_params = {
        "objective": "regression",
        "metric": "root_mean_squared_error",
        "learning_rate": params["learning_rate"],
        "max_depth": int(params["max_depth"]),
        "min_data_in_leaf": 5000,  # Fixed value
        "num_leaves": int(2 ** int(params["max_depth"]) * 0.65),
        "lambda_l1": params["lambda_l1"],  # Include L1 regularization
        "lambda_l2": params["lambda_l2"],  # Include L2 regularization
        "verbose": -1,
    }

    model, y_pred, eval_results = train_lightgbm(
        X_train, X_test, y_train, y_test, lightgbm_params
    )

    rmse = root_mean_squared_error(y_test, y_pred)
    return rmse


def train_fit_score_light_gbm(
    input_path: str, params, output_path: str, col_subset: list[str]
):
    cars = load_and_prepare_data(f"intermediate_data/{input_path}.parquet")
    if col_subset is not None:
        if "price" not in col_subset:
            col_subset.append("price")
        cars = cars[col_subset]

    model_name = "results/LightGBM"
    # Define the search space for Hyperopt (if not using predefined params)
    space = {
        "learning_rate": hp.uniform("learning_rate", 0.01, 0.3),
        "max_depth": hp.quniform("max_depth", 4, 10, 1),
        "lambda_l1": hp.uniform("lambda_l1", 0.0, 3.0),  # L1 regularization
        "lambda_l2": hp.uniform("lambda_l2", 0.0, 3.0),  # L2 regularization
    }

    # If no params are passed, run the optimization using Hyperopt's fmin
    if params is None:
        best_params = fmin(
            fn=lambda params: objective(params, cars, "price"),
            space=space,
            algo=tpe.suggest,
            max_evals=50,
        )
        # Convert float depth to int
        best_params["max_depth"] = int(best_params["max_depth"])
        model_name = model_name + "Hyperopt"
    else:
        # Use the provided params directly
        best_params = params

    if col_subset is not None:
        X_train, X_test, y_train, y_test = split_data(cars[col_subset], "price")
    else:
        X_train, X_test, y_train, y_test = split_data(cars, "price")
    # Prepare params for the final model
    final_params = {
        "objective": "regression",
        "metric": "root_mean_squared_error",
        "min_data_in_leaf": 2000,
        "learning_rate": best_params["learning_rate"],
        "max_depth": best_params["max_depth"],
        "num_leaves": int(2 ** int(best_params["max_depth"]) * 0.65),
        "lambda_l1": best_params["lambda_l1"],  # Include L1 regularization
        "lambda_l2": best_params["lambda_l2"],  # Include L2 regularization
        "verbose": -1,
    }

    model, y_pred, evals_result = train_lightgbm(
        X_train, X_test, y_train, y_test, final_params
    )
    model_name = model_name + "/"

    if output_path is not None:
        model_name = output_path
    evaluate_model(y_test, y_pred, model_name)
    plot_results(y_test, y_pred, model_name)
    plot_rmse_over_rounds(evals_result, model_name)

    # Save the model and parameters
    with open(f"{model_name}/best_lightgbm_model.pkl", "wb") as file:
        pickle.dump(model, file)
    with open(f"{model_name}/final_params.pkl", "wb") as file:
        pickle.dump(final_params, file)


def plot_rmse_over_rounds(evals_result, save_path):
    plt.figure(figsize=(10, 5))
    print(evals_result)
    train_rmse = evals_result["training"]["rmse"]
    valid_rmse = evals_result["validation"]["rmse"]

    plt.plot(train_rmse, label="Training RMSE", color="blue")
    plt.plot(valid_rmse, label="Validation RMSE", color="orange")
    plt.xlabel("Boosting Rounds")
    plt.ylabel("RMSE")
    plt.title("RMSE Across Boosting Rounds")
    plt.legend()

    directory = os.path.dirname(f"{save_path}")
    if not os.path.exists(directory):
        os.makedirs(directory)

    plt.savefig(f"{save_path}/rmse_over_rounds.png")
    plt.close()


# Example usage
# train_fit_score_light_gbm("your_file_name")
