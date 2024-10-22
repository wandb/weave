import base64
import io

import openai
import streamlit as st
from PIL import Image, ImageDraw
from streamlit_drawable_canvas import st_canvas

import weave

weave.init("testing161")


@st.cache_data
def get_dataset_rows(selected_option):
    ds = weave.ref(selected_option).get()
    return [dict(row) for row in ds.rows]


def simple_dropdown_ui():
    # Create a dropdown menu
    datasets = [
        "weave:///megatruong/call-dataset3/object/Dataset:mD6h0JglhIxmzXOydrqV7vv3tcwxDWP3dHhUBhLc7A8",
        "weave:///megatruong/call-dataset3/object/Dataset:Tz6gHUXvvSezHUPX1vX5hACjoFfDGNl6Pz1HRKUweuc",
    ]
    options = [weave.ref(d).uri() for d in datasets]
    selected_option = st.selectbox("Choose an option:", options)

    rows = get_dataset_rows(selected_option)
    # Create a nice rendering of the rows with editable fields
    st.write("Dataset Contents:")

    # Add navigation carousel
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0

    # Create a list of options for the carousel
    carousel_options = [f"Row {i+1}" for i in range(len(rows))]

    # Calculate the range of indices to display in the carousel
    start_index = max(0, st.session_state.current_index - 5)
    end_index = min(len(rows) - 1, st.session_state.current_index + 5)

    # Create a list of options for the carousel
    carousel_options = []
    carousel_images = []

    for i in range(start_index, end_index + 1):
        carousel_options.append(f"Row {i+1}")
        if "img" in rows[i]:
            img = rows[i]["img"]
            # Create a thumbnail
            thumb = img.copy()
            thumb.thumbnail((100, 100))
            carousel_images.append(thumb)
        else:
            carousel_images.append(None)

    # Display thumbnails
    cols = st.columns(len(carousel_options))
    for i, (option, image) in enumerate(zip(carousel_options, carousel_images)):
        with cols[i]:
            if image:
                st.image(image, caption=option, use_column_width=True)
            else:
                st.write(option)
                st.write("No image")

    # Create the carousel
    selected_row = st.select_slider(
        "Navigate through rows:",
        options=carousel_options,
        value=carousel_options[st.session_state.current_index],
        key="row_carousel",
    )

    # Update the current index based on the carousel selection
    st.session_state.current_index = carousel_options.index(selected_row)

    # Display the current row
    i = st.session_state.current_index
    row = rows[i]

    st.write(f"Row {i + 1} of {len(rows)}")
    for key, value in row.items():
        if key != "img":  # We'll display the image separately
            if isinstance(value, str):
                new_value = st.text_input(f"{key}", value, key=f"{i}_{key}")
                if new_value != value:
                    st.markdown(
                        f'<span style="color:red; background-color:#ffcccc;">~~{value}~~</span> → <span style="color:green; background-color:#ccffcc;">*{new_value}*</span>',
                        unsafe_allow_html=True,
                    )
                row[key] = new_value
            elif isinstance(value, (int, float)):
                new_value = st.number_input(f"{key}", value=value, key=f"{i}_{key}")
                if new_value != value:
                    st.markdown(
                        f'<span style="color:red; background-color:#ffcccc;">~~{value}~~</span> → <span style="color:green; background-color:#ccffcc;">*{new_value}*</span>',
                        unsafe_allow_html=True,
                    )
                row[key] = new_value
            elif isinstance(value, bool):
                new_value = st.checkbox(f"{key}", value, key=f"{i}_{key}")
                if new_value != value:
                    st.markdown(
                        f'<span style="color:red; background-color:#ffcccc;">~~{value}~~</span> → <span style="color:green; background-color:#ccffcc;">*{new_value}*</span>',
                        unsafe_allow_html=True,
                    )
                row[key] = new_value
            else:
                st.write(f"**{key}:** {value}")

    if "img" in row:
        img = row["img"]
        # Create a drawing object
        draw = ImageDraw.Draw(img)
        # Allow user to draw on the image
        img_width, img_height = img.size
        # Ensure the image is at least 512 pixels on each dimension
        canvas_width = max(512, img_width)
        canvas_height = max(512, img_height)
        # Calculate scaling factors
        scale_x = canvas_width / img_width
        scale_y = canvas_height / img_height
        # Use the smaller scaling factor to maintain aspect ratio
        scale = min(scale_x, scale_y)
        # Calculate new dimensions
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        # Resize the image
        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",  # Set fill color to semi-transparent orange
            stroke_width=2,
            stroke_color="#e00",
            background_image=resized_img,
            width=new_width,
            height=new_height,
            drawing_mode="freedraw",
            key=f"canvas_{i}",
        )
        # If the canvas was used (i.e., image was marked up)
        if canvas_result.image_data is not None:
            # Convert the canvas result to an image
            canvas_image = Image.fromarray(
                canvas_result.image_data.astype("uint8"), "RGBA"
            )

            # Create a composite image with the original image as the base
            marked_up_image = Image.alpha_composite(
                resized_img.convert("RGBA"), canvas_image
            )

            # Add a text box for annotation
            annotation = st.text_area("Describe what you drew:", key=f"annotation_{i}")

            # Save button
            if st.button("Save Marked-up Image and Annotation"):
                # Convert the marked-up image to bytes
                buffered = io.BytesIO()
                marked_up_image.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()

                # Save the image and annotation
                row["img"] = img_bytes
                row["annotation"] = annotation
                st.success("Marked-up image and annotation saved successfully!")

    # Add a button to process the annotation and drawing with GPT-4
    if st.button("Process with GPT-4"):
        # Ensure we have both an annotation and a marked-up image
        if annotation and canvas_result.image_data is not None:
            # Convert the marked-up image to a base64 string
            buffered = io.BytesIO()
            marked_up_image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            # Prepare the prompt for GPT-4
            prompt = f"""
            Analyze the following image and its corresponding annotation:

            Image: [Base64 encoded image data]
            Annotation: {annotation}

            Describe what the annotation highlights about the image and
            give it a score of 1-5 on how well it captures the annotation.
            """

            # Call GPT-4 API (you'll need to implement this function)
            gpt4_response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {
                        "role": "user",
                        "content": [
                            prompt,
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_str}"
                                },
                            },
                        ],
                    },
                ],
            )

            # Display the GPT-4 response
            st.subheader("GPT-4 Analysis")
            st.write(gpt4_response)
        else:
            st.warning(
                "Please provide both an annotation and a marked-up image before processing with GPT-4."
            )

    # Add a separator between the row details and the selected image
    st.markdown("---")


def handle_star_rating():
    # Custom star rating
    st.markdown(
        """
        <style>
        .star-rating {
            font-size: 0;
            white-space: nowrap;
            display: inline-block;
            width: 250px;
            height: 50px;
            overflow: hidden;
            position: relative;
            background: url('data:image/svg+xml;base64,PHN2ZyB2ZXJzaW9uPSIxLjEiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgeG1sbnM6eGxpbms9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGxpbmsiIHg9IjBweCIgeT0iMHB4IiB3aWR0aD0iMjBweCIgaGVpZ2h0PSIyMHB4IiB2aWV3Qm94PSIwIDAgMjAgMjAiIGVuYWJsZS1iYWNrZ3JvdW5kPSJuZXcgMCAwIDIwIDIwIiB4bWw6c3BhY2U9InByZXNlcnZlIj48cG9seWdvbiBmaWxsPSIjREREREREIiBwb2ludHM9IjEwLDAgMTMuMDksNi41ODMgMjAsNy42MzkgMTUsMTIuNzY0IDE2LjE4LDIwIDEwLDE2LjU4MyAzLjgyLDIwIDUsMTIuNzY0IDAsNy42MzkgNi45MSw2LjU4MyAiLz48L3N2Zz4=');
            background-size: contain;
        }
        .star-rating i {
            opacity: 0;
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: 20%;
            z-index: 1;
            background: url('data:image/svg+xml;base64,PHN2ZyB2ZXJzaW9uPSIxLjEiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgeG1sbnM6eGxpbms9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGxpbmsiIHg9IjBweCIgeT0iMHB4IiB3aWR0aD0iMjBweCIgaGVpZ2h0PSIyMHB4IiB2aWV3Qm94PSIwIDAgMjAgMjAiIGVuYWJsZS1iYWNrZ3JvdW5kPSJuZXcgMCAwIDIwIDIwIiB4bWw6c3BhY2U9InByZXNlcnZlIj48cG9seWdvbiBmaWxsPSIjRkZERjg4IiBwb2ludHM9IjEwLDAgMTMuMDksNi41ODMgMjAsNy42MzkgMTUsMTIuNzY0IDE2LjE4LDIwIDEwLDE2LjU4MyAzLjgyLDIwIDUsMTIuNzY0IDAsNy42MzkgNi45MSw2LjU4MyAiLz48L3N2Zz4=');
            background-size: contain;
        }
        .star-rating input {
            -moz-appearance: none;
            -webkit-appearance: none;
            opacity: 0;
            display: inline-block;
            width: 20%;
            height: 100%;
            margin: 0;
            padding: 0;
            z-index: 2;
            position: relative;
        }
        .star-rating input:hover + i,
        .star-rating input:checked + i {
            opacity: 1;
        }
        .star-rating i ~ i {
            width: 40%;
        }
        .star-rating i ~ i ~ i {
            width: 60%;
        }
        .star-rating i ~ i ~ i ~ i {
            width: 80%;
        }
        .star-rating i ~ i ~ i ~ i ~ i {
            width: 100%;
        }
        </style>

        <span class="star-rating">
            <input type="radio" name="rating" value="1"><i></i>
            <input type="radio" name="rating" value="2"><i></i>
            <input type="radio" name="rating" value="3"><i></i>
            <input type="radio" name="rating" value="4"><i></i>
            <input type="radio" name="rating" value="5"><i></i>
        </span>

        <script>
        const starRating = document.querySelector('.star-rating');
        let rating = 0;
        starRating.addEventListener('change', (e) => {
            rating = e.target.value;
            window.parent.postMessage({type: 'rating', value: rating}, '*');
        });
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Use session state to store the rating
    if "rating" not in st.session_state:
        st.session_state.rating = 0

    # JavaScript to update session state
    st.markdown(
        """
        <script>
        window.addEventListener('message', function(e) {
            if (e.data.type === 'rating') {
                window.parent.postMessage({type: 'streamlit:set_widget_value', key: 'rating', value: e.data.value}, '*');
            }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Display the current rating
    st.write(f"Current Rating: {st.session_state.rating}")


def display_annotation_options():
    # Add annotation options to the right sidebar
    with st.sidebar.container():
        st.header("Annotation Options")

        handle_star_rating()

        # Short text description
        description = st.text_area("Short Description", height=100)

        # Confidence level
        confidence = st.select_slider(
            "Confidence Level",
            options=["Very Low", "Low", "Medium", "High", "Very High"],
            value="Medium",
        )

        # Tags input
        tags = st.text_input("Tags (comma-separated)")

        # Checkbox for data quality
        is_high_quality = st.checkbox("High Quality Data")

        # Button to save annotations
        if st.button("Save Annotations"):
            st.success("Annotations saved successfully!")

        # Display current annotations
        st.subheader("Current Annotations")
        st.write(f"Rating: {st.session_state.rating}")
        st.write(f"Description: {description}")
        st.write(f"Confidence: {confidence}")
        st.write(f"Tags: {tags}")
        st.write(f"High Quality: {'Yes' if is_high_quality else 'No'}")


# Call the function to display the UI
simple_dropdown_ui()
display_annotation_options()
