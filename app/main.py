from flask import render_template, session
from app import webapp


@webapp.route('/', methods=['GET'])
def main():
    session.clear()
    return render_template("main.html", title="Home Page")
