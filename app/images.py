from flask import render_template, redirect, url_for, request, g, session
from app import webapp
from wand.image import Image

import os
import mysql.connector

from app.config import db_config

APP_ROOT = os.path.dirname(os.path.abspath(__file__))


# ================== Database Function ==================
def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'])


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db


@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# ================== Main Feature Function ==================
@webapp.route('/user/authenticated/<user_id>', methods=['GET'])
def user_profile(user_id):
    if 'authenticated_user_'+str(user_id) not in session:
        return redirect(url_for('main'))

    # Get username
    username = get_username(user_id)

    # Get thumbnail list
    thumbnail_list = {}
    cnx = get_db()
    cursor = cnx.cursor()
    query = '''SELECT * FROM imageset im, userimage ui, userprofile up 
                WHERE up.id = %s AND up.id = ui.user_id AND ui.image_id = im.id'''

    cursor.execute(query, (user_id,))
    # User doesn't have any image saved in database yet
    if not cursor:
        return render_template("user/profile.html", title="Welcome Back!", username=username, user_id=user_id)

    else:
        for row in cursor:
            # Load thumbnail_urls
            thumbnail_list[row[1]] = row[3]
            print(thumbnail_list)

        # Display thumbnails, title and username on user's profile page
        return render_template("user/profile.html", title="Welcome Back!", imgList=thumbnail_list,
                               username=username.upper(), user_id=user_id)


@webapp.route('/user/authenticated/<user_id>/upload', methods=['POST'])
def image_upload(user_id):

    # Create 'local_images' folder for storing uploaded images
    target = os.path.join(APP_ROOT, 'static/')

    # If local_image folder not exist
    if not os.path.isdir(target):
        os.mkdir(target)

    image_url_list = []

    # Process each image
    for file in request.files.getlist("file"):
        if not file:
            print('2222222222222')
            return redirect(url_for('user_profile', user_id=user_id))
        # Get filename
        filename = file.filename
        print('=========== Dealing with ' + filename + ' ===========')

        # Save file to user's static folder
        destination = "".join([target, filename])
        file.save(destination)

        # Generate relative path for html display
        original_url = url_for('static', filename=filename)
        print(original_url)

        trans_url = image_transformation(filename)
        image_url_list.append(original_url)
        for each in trans_url:
            image_url_list.append(each)
        print(image_url_list)

        # Update/insert those urls into database
        check_path(image_url_list, user_id, filename)
        print('=========== ' + filename + ' has been saved to database successfully ===========')

        # Clear image_url_list before processing next image
        image_url_list = []

    return redirect(url_for('user_profile', user_id=user_id))


@webapp.route('/user/authenticated/<user_id>/<filename>', methods=['GET'])
def image_detail(user_id, filename):
    # Get image id based on thumb_url and user_id
    print('=========== Getting Image Detail ===========')
    cnx = get_db()
    cursor = cnx.cursor()

    query = '''SELECT im.original, im.grey, im.mirror, im.color 
            FROM userprofile up, userimage ui, imageset im 
            WHERE up.id = %s AND up.id = ui.user_id AND ui.image_id = im.id AND im.name = %s'''
    cursor.execute(query, (user_id, filename,))

    row = cursor.fetchone()
    print('=========== Fetch Complete ===========')
    original_url = row[0]
    grey_url = row[1]
    mirror_url = row[2]
    color_url = row[3]
    print('=========== Displaying All Images ===========')
    return render_template("image/detail.html", filename=filename, original_img=original_url, grey_img=grey_url,
                           mirror_img=mirror_url, color_img=color_url, user_id=user_id)


@webapp.route('/user/authenticated/<user_id>/<filename>/delete', methods=['GET'])
def delete_image(user_id, filename):
    cnx = get_db()
    cursor = cnx.cursor()

    query = '''SELECT im.id FROM userprofile up, userimage ui, imageset im 
                WHERE up.id = %s AND up.id = ui.user_id AND ui.image_id = im.id AND im.name = %s'''
    cursor.execute(query, (user_id, filename,))
    row = cursor.fetchone()
    image_id = row[0]

    query = "DELETE FROM imageset WHERE id = %s"
    cursor.execute(query, (image_id,))
    cnx.commit()
    return redirect(url_for('user_profile', user_id=user_id))


# ================== Helper Function ==================
# Get username from user_id
def get_username(user_id):
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT username FROM userprofile WHERE id = %s"
    cursor.execute(query, (user_id,))
    row = cursor.fetchone()
    username = row[0]
    return username


# Check the target image, save into database if not exist before
def check_path(urlset, user_id, filename):
    cnx = get_db()
    cursor = cnx.cursor(buffered=True)
    query = '''SELECT * FROM imageset im, userimage ui, userprofile up 
                WHERE up.id = %s AND up.id = ui.user_id AND ui.image_id = im.id AND im.name = %s'''
    cursor.execute(query, (user_id, filename,))
    row = cursor.fetchone()
    # Check if we already have this image with same filename for this user
    # If not, save this new image info into database
    # print('Cursor is:' + cursor)
    if not row:
        query = "INSERT INTO imageset (name, original, thumbnail, grey, mirror, color) VALUES (%s, %s, %s, %s, %s, %s)"
        cursor.execute(query, (filename, urlset[0], urlset[1], urlset[2], urlset[3], urlset[4],))
        cnx.commit()
        # Get image_id from this newly added image
        query = "SELECT id FROM imageset WHERE original = %s"
        cursor.execute(query, (urlset[0],))
        row_img = cursor.fetchone()
        image_id = row_img[0]
        # Get image_id for the image, pair user_id and image_id into connection table
        query = "INSERT INTO userimage (user_id, image_id) VALUES (%s, %s)"
        cursor.execute(query, (user_id, image_id,))
        cnx.commit()

    # If cursor exist, we don't need to do anything
    else:
        print('=========== Image Already Exists ===========')
        pass


# Generate 1 thumbnail and 3 transformed images from original one
def image_transformation(name):
    total_url = []
    # Perform transformation and return those newly created images' url
    thumb_url = image_thumbnail(name)
    seam_url = image_grey_scale(name)
    mirror_url = image_mirror(name)
    color_url = image_color_enhance(name)
    # Collect those url and return the result
    total_url.append(thumb_url)
    total_url.append(seam_url)
    total_url.append(mirror_url)
    total_url.append(color_url)
    return total_url


# Create thumbnail of image, return thumbnail url
def image_thumbnail(name):
    name_path = os.path.join('app/static', name)
    with Image(filename=name_path).clone() as img:
        img.resize(320, 240)
        # Add prefix to filename and save as new image file
        prefix = 'thumbnail_'
        new_name_path = os.path.join('app/static', prefix + name)
        img.save(filename=new_name_path)
    return url_for('static', filename=prefix + name)


# Apply grey scale filter onto images, return grey url
def image_grey_scale(name):
    name_path = os.path.join('app/static', name)
    with Image(filename=name_path).clone() as img:
        img.type = 'grayscale'
        # Add prefix to filename and save as new image file
        prefix = 'grey_'
        new_name_path = os.path.join('app/static', prefix + name)
        img.save(filename=new_name_path)
    return url_for('static', filename=prefix + name)


# Create mirror-version of image, return mirror url
def image_mirror(name):
    name_path = os.path.join('app/static', name)
    with Image(filename=name_path).clone() as flopped:
        flopped.flop()
        # Add prefix to filename and save as new image file
        prefix = 'mirror_'
        new_name_path = os.path.join('app/static', prefix + name)
        flopped.save(filename=new_name_path)
    return url_for('static', filename=prefix + name)


# Enhance the color of image, return color url
def image_color_enhance(name):
    name_path = os.path.join('app/static', name)
    with Image(filename=name_path).clone() as img:
        # B >> 1
        img.evaluate(operator='rightshift', value=1, channel='blue')
        # R << 1
        img.evaluate(operator='leftshift', value=1, channel='red')
        # Add prefix to filename and save as new image file
        prefix = 'colored_'
        new_name_path = os.path.join('app/static', prefix + name)
        img.save(filename=new_name_path)
    return url_for('static', filename=prefix + name)
