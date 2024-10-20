import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import r2_score, root_mean_squared_error
import statsmodels.api as sm
import os


def train_fit_score_linear_regression(X, y, log: bool, one_hot_encode: bool):
    if one_hot_encode:
        X = one_hot_columns(X)
    # Add a constant term for the intercept (as statsmodels does not include it by default)
    X = sm.add_constant(X)

    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Create and fit the linear regression model using statsmodels
    model = sm.OLS(y_train, X_train).fit()

    # Make predictions on the test set
    y_pred = model.predict(X_test)
    if log:
        y_pred = np.exp(y_pred)
        y_test = np.exp(y_test)

    plot_results(y_test, y_pred, log)
    print_results(y_test, y_pred, model)
    return model


def plot_results(y_test, y_pred, log):
    # Plot predicted vs actual values
    plt.figure(figsize=(10, 5))

    # Plot 1: Predicted vs Actual values
    plt.subplot(1, 2, 1)
    plt.scatter(y_test, y_pred, edgecolor="k", alpha=0.7)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], "r--", lw=2)
    plt.xlabel("Actual")
    plt.ylabel("Predicted")
    plt.title("Predicted vs Actual")

    # Plot 2: Residuals plot
    plt.subplot(1, 2, 2)
    residuals = y_test - y_pred
    plt.scatter(y_pred, residuals, edgecolor="k", alpha=0.7)
    plt.axhline(y=0, color="r", linestyle="--", lw=2)
    plt.xlabel("Predicted")
    plt.ylabel("Residuals")
    plt.title("Residuals Plot")

    plt.tight_layout()

    if log:
        model_name = "Log price Linear Regression/"
    else:
        model_name = "Simple Linear Regression of Price by Odometer/"

    save_path = "output/"
    # Ensure the directory exists
    directory = os.path.dirname(f"{save_path}{model_name}")
    if not os.path.exists(directory):
        os.makedirs(directory)

    plt.savefig(f"{directory}/predicted_vs_actual.png")  # Save Predicted vs Actual plot


def print_results(y_test, y_pred, model):
    # Calculate RMSE and R2 score
    rmse = np.sqrt(root_mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"Root Mean Squared Error (RMSE): {rmse}")
    print(f"R-squared (R2): {r2}")

    # Print the summary of the regression model (including beta coefficients, p-values, F-statistic, etc.)
    print("\nModel Summary:")
    print(model.summary())


def one_hot_columns(cars):
    # Create an empty list to store processed columns
    processed_columns = []

    # Initialize OneHotEncoder
    encoder = OneHotEncoder(drop="first", sparse_output=False)

    # Step 1: Process each column based on its dtype
    for col in cars.columns:
        if cars[col].dtype == "bool":  # Convert boolean columns to integers
            cars[col] = cars[col].astype(int)
            processed_columns.append(cars[[col]])  # Append processed column

        elif cars[col].dtype == "object":  # One-hot encode string/categorical columns
            encoded = encoder.fit_transform(cars[[col]])
            encoded_cars = pd.DataFrame(
                encoded, columns=encoder.get_feature_names_out([col])
            )
            processed_columns.append(encoded_cars)  # Append one-hot encoded columns

        elif col != "price":  # Include numeric columns as they are
            processed_columns.append(cars[[col]])

    X = pd.concat(processed_columns, axis=1)
    return X
