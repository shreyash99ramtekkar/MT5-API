# Use an official Python runtime as a parent image
FROM python:3.10.12

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

RUN chmod +x ./wait-for-it.sh

# Install any dependencies from requirements.txt
RUN pip install -r ./requirement.txt

EXPOSE 5000

# Run app.py when the container launches
CMD ["python", "app.py"]

