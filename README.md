# Project Manager Dashboard

A modern, beautiful dashboard to manage all your Dockerized projects from any computer or server.

---

✨ **Made with ❤️ by [@esjavadex](https://github.com/esjavadex)** ✨

---

## Features
- Gorgeous landing page
- Admin panel with project management
- Docker container control interface
- Responsive design (works on mobile)
- Works on any Linux, Mac, or Windows machine with Docker

## Technologies
- Python Flask backend
- Tailwind CSS for styling
- Docker API integration
- SQLite database (for user auth)

## Setup
1. Clone this repository
2. Run `pip install -r requirements.txt`
3. Configure `.env` file
4. Run `python app.py`

## Docker Setup
1. Build the image: `docker-compose build`
2. Run the container: `docker-compose up`
3. Access the app at: http://localhost:5000

**Note**: The container needs access to your host's Docker daemon to manage other containers.
