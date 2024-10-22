from __future__ import annotations
import polars as pl
from sklearn.impute import SimpleImputer
import zipfile
from pathlib import Path


def unzip_and_load_csv(zip_file_path: str, output_directory: str) -> pl.DataFrame:
    zip_file_path = Path(zip_file_path)
    output_directory = Path(output_directory)

    # Unzip the file
    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(output_directory)

    print(f"Files extracted to {output_directory}")

    # Load the CSV file into a Polars DataFrame
    csv_file_path = output_directory / "vehicles.csv"
    return pl.read_csv(csv_file_path)


# This function was sadly shuttered as I was getting all sorts of werid hisenbugs
# thread '<unnamed>' panicked at crates\polars-core\src\series\from.rs:117:22:
# called `Option::unwrap()` on a `None` value
# note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
# Traceback (most recent call last):
#   File "c:\git_repos\video_game_sales\video_game_sales_predictions\master_script.py", line 78, in <module>
#     cars_imputed_missing_for_lin_regrs.write_parquet(
#   File "C:\git_repos\video_game_sales\video_game_sales_predictions\venv\Lib\site-packages\polars\dataframe\frame.py", line 3837, in write_parquet
#     self._df.write_parquet(
# pyo3_runtime.PanicException: called `Option::unwrap()` on a `None` value
# PS C:\git_repos\video_game_sales\video_game_sales_predictions> ^C

# def clean_cylinders_column(cars: pl.DataFrame) -> pl.DataFrame:
#     cars = cars.with_columns(
#         pl.when(pl.col("cylinders").is_not_null() & (pl.col("cylinders") != ""))
#         .then(pl.col("cylinders").str.replace_all(r"\D", ""))
#         .otherwise(pl.lit(""))
#         .cast(pl.Utf8)
#         .alias("cylinders")
#     )

#     cars = cars.with_columns(
#         pl.when(pl.col("cylinders") == "")
#         .then(pl.lit(None))
#         .otherwise(pl.col("cylinders"))
#         .cast(pl.Utf8)
#         .alias("cylinders")
#     )
#     return cars


def drop_unnecessary_columns(cars: pl.DataFrame) -> pl.DataFrame:
    return cars.drop(
        "id", "url", "region_url", "VIN", "image_url", "county", "posting_date", "size"
    )


def detect_if_description_exists(cars: pl.DataFrame) -> pl.DataFrame:
    if "description" not in cars.columns:
        raise ValueError("The column 'description' does not exist in the DataFrame.")

    cars = cars.with_columns(
        (pl.col("description").is_not_null() & (pl.col("description") != "")).alias(
            "description_exists"
        )
    )
    return cars


def delete_description_if_caravana(cars: pl.DataFrame) -> pl.DataFrame:
    cars = cars.with_columns(
        pl.when(pl.col("carvana_ad"))
        .then(pl.lit(""))
        .otherwise(pl.col("description"))
        .alias("description")
    )
    return cars


def detect_if_carvana_ad(cars: pl.DataFrame) -> pl.DataFrame:
    cars = cars.with_columns(
        (
            pl.col("description")
            .fill_null("")
            .str.to_lowercase()
            .str.contains("carvana is the safer way to buy a car")
        ).alias("carvana_ad")
    )
    return cars


def null_out_impossible_values(cars, col, upper_col_limit: int) -> pl.DataFrame:
    cars = cars.with_columns(pl.col(col).cast(pl.Int64))
    rows_to_nullify = cars.filter(pl.col(col) > upper_col_limit).height

    cars = cars.with_columns(
        pl.when(pl.col(col) > upper_col_limit)
        .then(None)
        .otherwise(pl.col(col))
        .alias(col)
    )

    # Log the filter and number of rows affected
    print(f"Filter applied: {col} > {upper_col_limit}")
    print(f"Rows set to none: {rows_to_nullify}")
    return cars


def drop_out_impossible_values(cars, col, col_limit, upper: True) -> pl.DataFrame:
    cars = cars.with_columns(pl.col(col).cast(pl.Int64))
    if upper:
        rows_to_nullify = cars.filter(pl.col(col) > col_limit).height

        cars = cars.filter(pl.col(col) < col_limit)
        # Log the filter and number of rows affected
        print(f"Filter applied: {col} >  {col_limit}")
    else:
        rows_to_nullify = cars.filter(pl.col(col) < col_limit).height

        cars = cars.filter(pl.col(col) > col_limit)
        # Log the filter and number of rows affected
        print(f"Filter applied: {col} <  {col_limit}")
    print(f"Rows removed: {rows_to_nullify}")
    return cars


def remove_duplicate_rows(cars: pl.DataFrame) -> pl.DataFrame:
    cars = cars.unique()
    return cars


def fill_missing_values_column_level(
    df: pl.DataFrame, columns: list[str]
) -> pl.DataFrame:
    # Prepare a copy of the DataFrame to avoid modifying the original
    updated_df = df.clone()

    for col in columns:
        if col in df.columns:
            # Determine the data type of the column
            col_type = df.schema[col]

            # Convert the selected column to a NumPy array
            data = updated_df[col].to_numpy().reshape(-1, 1)  # Reshape for the imputer

            # Create the appropriate imputer
            if col_type == pl.Int64 or col_type == pl.UInt32:
                imputer = SimpleImputer(strategy="mean")
            elif col_type == pl.Utf8:
                imputer = SimpleImputer(strategy="most_frequent")
            else:
                continue  # Skip unsupported types

            # Impute missing values
            imputed_data = imputer.fit_transform(data)

            # Update the DataFrame with the imputed values
            updated_df = updated_df.with_columns(
                pl.Series(name=col, values=imputed_data.flatten())
            )

    return updated_df


def switch_condition_to_ordinal(cars: pl.DataFrame):
    # this is subjective and open to SME.
    ordinal_mapping = {
        "salvage": -3,
        "fair": -2,
        "good": -1,
        "excellent": 1,
        "new": 2,
        "like new": 2,
    }
    cars = cars.with_columns(
        pl.col("condition").replace(ordinal_mapping).alias("condition")
    )
    return cars