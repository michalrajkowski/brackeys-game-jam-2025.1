from PIL import Image

# Load the image
image = Image.open("image.png")  # Replace with your image path

# Resize the image to 128x128 pixels
resized_image = image.resize((128, 128))

# Save the resized image
resized_image.save("epic_duck.png")  # Replace with your desired output path

# Optionally, show the resized image
resized_image.show()
