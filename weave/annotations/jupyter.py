import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from IPython.display import display
from ipywidgets import widgets
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer

import weave


class DataFrameAnnotator:
    def __init__(
        self,
        df: pd.DataFrame,
        save_file: str = "annotations.json",
        hover_column: str = "output.sentence",
    ) -> None:
        self.df = df
        self.fig = go.FigureWidget()
        self.selected_points: list[int] = []
        self.save_file = save_file
        self.annotations: list[dict] = []
        self.current_colors = ["blue"] * len(df)
        self.current_labels = [""] * len(df)
        self.temp_colors = self.current_colors.copy()
        self.hover_column = hover_column

        self.x_dropdown = widgets.Dropdown(description="X-axis:")
        self.y_dropdown = widgets.Dropdown(description="Y-axis:")
        self.hover_dropdown = widgets.Dropdown(description="Hover text:")

        self.x_dropdown.observe(self.update_plot, names="value")
        self.y_dropdown.observe(self.update_plot, names="value")
        self.hover_dropdown.observe(self.update_plot, names="value")

        self.color_picker = widgets.ColorPicker(description="Color:")
        self.color_picker.observe(self.update_color, names="value")
        self.label_input = widgets.Text(description="Label:")
        self.apply_button = widgets.Button(description="Apply Label")
        self.apply_button.on_click(self.save_selection)

        self.widget = widgets.VBox(
            [
                widgets.HBox([self.x_dropdown, self.y_dropdown, self.hover_dropdown]),
                widgets.HBox([self.color_picker, self.label_input, self.apply_button]),
                self.fig,
            ]
        )

        self.update_dropdowns()
        self.load_annotations()

    def update_dropdowns(self) -> None:
        numeric_columns = self.df.select_dtypes(include=[np.number]).columns
        all_columns = self.df.columns
        self.x_dropdown.options = numeric_columns
        self.y_dropdown.options = numeric_columns
        self.hover_dropdown.options = all_columns
        if len(numeric_columns) > 0:
            self.x_dropdown.value = numeric_columns[0]
        if len(numeric_columns) > 1:
            self.y_dropdown.value = numeric_columns[1]
        if self.hover_column in all_columns:
            self.hover_dropdown.value = self.hover_column
        elif len(all_columns) > 0:
            self.hover_dropdown.value = all_columns[0]

    def update_plot(self, _) -> None:
        if not all(
            [self.x_dropdown.value, self.y_dropdown.value, self.hover_dropdown.value]
        ):
            return

        x = self.df[self.x_dropdown.value]
        y = self.df[self.y_dropdown.value]
        hover_text = self.df[self.hover_dropdown.value]

        formatted_hover_text = []
        for i, label in enumerate(self.current_labels):
            text = f"x: {x[i]}<br>" f"y: {y[i]}<br>" f"label: {label}<br>"

            # Process hover text separately
            hover_lines = []
            current_line = f"{self.hover_dropdown.value}: "
            for word in str(hover_text[i]).split():
                if len(current_line) + len(word) + 1 > 50:
                    hover_lines.append(current_line)
                    current_line = word
                else:
                    current_line += " " + word if current_line else word
            hover_lines.append(current_line)

            # Add up to 3 lines of hover text
            text += "<br>".join(hover_lines[:3])
            formatted_hover_text.append(text)

        self.fig.data = []
        self.scatter = self.fig.add_scatter(
            x=x,
            y=y,
            mode="markers",
            name="Data",
            marker=dict(color=self.temp_colors),
            text=self.current_labels,
            hoverinfo="text",
            hovertext=formatted_hover_text,
        )

        self.fig.layout.title = f"{self.x_dropdown.value} vs {self.y_dropdown.value}"
        self.fig.layout.xaxis.title = self.x_dropdown.value
        self.fig.layout.yaxis.title = self.y_dropdown.value

        self.fig.layout.dragmode = "lasso"
        self.fig.layout.hovermode = "closest"

        self.fig.data[0].on_selection(self.selection_fn)

    def selection_fn(self, trace, points, selector) -> None:
        self.selected_points = points.point_inds
        print(f"Selected points: {self.selected_points}")
        self.update_color(None)

    def update_color(self, change) -> None:
        if self.selected_points:
            color = self.color_picker.value
            for point in self.selected_points:
                self.temp_colors[point] = color
            self.fig.data[0].marker.color = self.temp_colors

    def save_selection(self, _) -> None:
        if not self.selected_points:
            return

        color = self.color_picker.value
        label = self.label_input.value

        for point in self.selected_points:
            self.current_colors[point] = color
            self.current_labels[point] = label

        self.temp_colors = self.current_colors.copy()

        self.annotations = [
            {"points": [i], "color": color, "label": label}
            for i, (color, label) in enumerate(
                zip(self.current_colors, self.current_labels)
            )
            if color != "blue" or label != ""
        ]

        self.update_plot(None)
        self.save_annotations()
        print(f"Selection saved with label '{label}' and color {color}")

    def save_annotations(self) -> None:
        with open(self.save_file, "w") as f:
            json.dump(self.annotations, f)

    def load_annotations(self) -> None:
        if os.path.exists(self.save_file):
            with open(self.save_file, "r") as f:
                self.annotations = json.load(f)

            for annotation in self.annotations:
                for point in annotation["points"]:
                    self.current_colors[point] = annotation["color"]
                    self.current_labels[point] = annotation["label"]

            self.temp_colors = self.current_colors.copy()

    def display(self) -> None:
        display(self.widget)
        self.update_plot(None)

    def _repr_html_(self):
        from IPython.display import display

        display(self.widget)
        self.update_plot(None)
        return ""

    def get_selected_data(self) -> pd.DataFrame:
        df_with_annotations = self.df.copy()
        df_with_annotations["annotation_label"] = self.current_labels
        df_with_annotations["annotation_color"] = self.current_colors
        return df_with_annotations

    def with_pca(self) -> "DataFrameAnnotator":
        # Create TF-IDF vectorizer
        tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")

        # Get messages from the DataFrame
        df = self.df
        messages = df["output.message"].dropna().tolist()

        # Fit and transform the messages to TF-IDF vectors
        tfidf_matrix = tfidf_vectorizer.fit_transform(messages)

        # Convert sparse matrix to dense array
        tfidf_dense = tfidf_matrix.toarray()

        # Perform PCA on the TF-IDF vectors
        pca = PCA(n_components=5)
        pca_result = pca.fit_transform(tfidf_dense)

        # Add the PCAs back to the DataFrame
        pca_df = pd.DataFrame(pca_result, columns=[f"PCA_{i+1}" for i in range(5)])
        df = pd.concat([df, pca_df], axis=1)

        # Interpret and label each PCA
        for i in range(5):
            loadings = pca.components_[i]
            sorted_indices = np.argsort(loadings)
            top_positive = [
                tfidf_vectorizer.get_feature_names_out()[idx]
                for idx in sorted_indices[-5:]
            ]
            top_negative = [
                tfidf_vectorizer.get_feature_names_out()[idx]
                for idx in sorted_indices[:5]
            ]

            print(f"PCA_{i+1}:")
            print(f"  Positive end: {', '.join(top_positive)}")
            print(f"  Negative end: {', '.join(top_negative)}")
            print(f"  Variance explained: {pca.explained_variance_ratio_[i]:.2%}")
            print()

        self.df = df
        self.update_dropdowns()
        return self

    def export_to_dataset(
        self, *, publish: bool = True, name: str = "My annotated dataset"
    ) -> weave.Dataset:
        df = self.get_selected_data()
        ds = weave.Dataset(name=name, rows=df.to_dict(orient="records"))

        if publish:
            weave.publish(ds)

        return ds


class DatasetAnnotator(DataFrameAnnotator):
    def __init__(self, dataset: weave.Dataset):
        df = pd.json_normalize(dataset.rows)
        super().__init__(df)
