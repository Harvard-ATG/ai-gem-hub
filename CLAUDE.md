# Gem Hub - Project Notes

## Overview
A Flask app that serves as a homepage for Gemini Gems. Users can browse gems by category, save their favorites, and submit new bot requests for admin approval.

## Tech Stack
- **Backend**: Flask (Python)
- **Data Storage**: JSON files (no database)
- **Frontend**: Jinja2 templates, vanilla CSS/JS

## Project Structure
```
ai-home/
├── app.py              # Main Flask application
├── pyproject.toml      # Project metadata and dependencies (uv)
├── uv.lock             # Locked dependency versions
├── Dockerfile          # Container image definition
├── docker-compose.yml  # Docker Compose configuration
├── data/
│   ├── gems.json       # All gems with categories: student, university, school, admin, course
│   ├── saved.json      # User's saved gems
│   ├── schools.json    # List of schools (FAS, HLS, DCE)
│   └── requests.json   # Bot submission requests (pending/approved/rejected)
├── templates/
│   ├── index.html          # Main page (two-column layout)
│   ├── admin.html          # Admin list view
│   ├── admin_form.html     # Admin add/edit form
│   ├── admin_requests.html # Admin bot request review page
│   ├── request_form.html   # Public bot submission form
│   └── request_success.html # Submission confirmation page
├── static/
│   ├── style.css       # All styling
│   └── images/
│       └── gem.jpeg    # Header logo
```

## Key Features
- Five gem categories: University Gems, Course Gems, School Gems, Student Gems, Administrative Gems
- Two-column layout: categories on left, saved gems sidebar on right
- Bookmark icon to save/unsave gems (bottom right of card, crimson when saved)
- Search box above categories filters gems by name and description
- Search results replace categories and show category chips on cards; clearing search restores category view
- Opens gem URLs in new tab (external link icon on each card, color matches category)
- Header links: Share a Bot (crimson button), AI Guidelines (ghost button), HUIT Sandbox (solid green button)
- Admin page for managing gems (add, edit, delete)
- Public bot request form (Share a Bot) with admin approval workflow

## Color Scheme
- **Crimson/Red**: #A51C30 (header, bookmark icon when saved, Share a Bot button)
- **Turquoise**: #00aaad (buttons, saved section accent)
- **Green**: #4db848 (HUIT Sandbox button, AI Guidelines border)
- **University Gems**: #ec8f9c (pink)
- **Course Gems**: #946eb7 (purple)
- **School Gems**: #e67e22 (orange)
- **Student Gems**: #95b5df (blue)
- **Administrative Gems**: #fcb315 (gold)

## Running the App
Requires [uv](https://docs.astral.sh/uv/).
```bash
uv run python app.py
```
Then open http://localhost:5000

Or with Docker:
```bash
docker compose up --build
```

## API Endpoints
- `GET /` - Main page
- `POST /api/save/<gem_id>` - Save a gem
- `POST /api/unsave/<gem_id>` - Unsave a gem
- `GET /api/saved` - Get all saved gems (JSON)

## Bot Request Endpoints
- `GET /request` - Public bot submission form
- `POST /request` - Submit a new bot request
- `GET /request/success` - Submission confirmation page

## Admin Endpoints
- `GET /admin` - Admin list view (shows pending request count)
- `GET /admin/gem` - Add new gem form
- `POST /admin/gem` - Create new gem
- `GET /admin/gem/<gem_id>` - Edit gem form
- `POST /admin/gem/<gem_id>` - Update gem
- `POST /admin/delete/<gem_id>` - Delete gem
- `GET /admin/requests` - View pending and resolved bot requests
- `POST /admin/requests/<id>/approve` - Approve a request (creates gem)
- `POST /admin/requests/<id>/reject` - Reject a request

## Bot Request Data Model
```json
{
  "id": "req-<timestamp>",
  "requester_name": "", "requester_email": "", "school": "", "role": "",
  "bot_name": "", "bot_description": "", "bot_url": "",
  "bot_type": "gem|ai-assistant|other",
  "category": "university|school|course|student|admin",
  "status": "pending|approved|rejected",
  "submitted_at": "<ISO timestamp>"
}
```

## Approval Flow
1. User clicks "Share a Bot" in header → fills out form → saved to requests.json as "pending"
2. Admin sees pending count badge on admin page → clicks "Bot Requests"
3. Admin reviews, clicks Approve → gem created in gems.json, request marked approved
4. Gem appears on main page under its category

## Design Notes
- Header is 60px tall, left-aligned with logo
- Everything sized ~20% smaller than default for compact look
- White background, minimal design
- Cards have colored left border indicating category
- Cards are fixed 220px width, left-aligned in grid
- Saved gems sidebar (280px) on right, sticky positioning
- Category chips shown on saved cards and search results
- Search box left-aligned above categories
