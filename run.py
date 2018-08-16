import argparse
import os.path
import pathlib
import random

import safygiphy

# Own modules:
import goodreads
import google_images
import inspirobot
import os_util
import reddit
import shitpostbot
import slide_templates
import slide_topic_generators
import text_generator
import wikihow
# Import a lot from generator_util to make schema creation easier
from generator_util import create_seeded_generator, none_generator, create_static_generator, combined_generator, \
    create_from_external_image_list_generator, create_from_list_generator, \
    create_backup_generator, remove_invalid_images_from_generator, seeded_titled_identity_generator, \
    create_inspired_tuple_generator
from presentation_schema import PresentationSchema, SlideGenerator, constant_weight, create_peaked_weight

MAX_PRESENTATION_SAVE_TRIES = 100


# == HELPER FUNCTIONS ==
def _save_presentation_to_pptx(output_folder, file_name, prs, index=0):
    """Save the talk."""
    if index > MAX_PRESENTATION_SAVE_TRIES:
        return None

    suffix = "_" + str(index) if index > 0 else ""
    fp = os.path.join(output_folder, str(file_name) + str(suffix) + ".pptx")
    # Create the parent folder if it doesn't exist
    pathlib.Path(os.path.dirname(fp)).mkdir(parents=True, exist_ok=True)
    try:
        prs.save(fp)
        print('Saved talk to {}'.format(fp))
        return fp
    except PermissionError:
        index += 1
        return _save_presentation_to_pptx(output_folder, file_name, prs, index)


# == MAIN ==

def main(arguments):
    """Make a talk with the given topic."""
    # Print status details
    print('******************************************')
    print("Making {} slide talk on: {}".format(arguments.num_slides, arguments.topic))

    # Retrieve the schema to generate the presentation with
    schema = get_schema(arguments.schema)

    # Generate random presenter name if no presenter name given
    if not arguments.presenter:
        arguments.presenter = full_name_generator()

    # Generate the presentation object
    presentation = schema.generate_presentation(topic=arguments.topic,
                                                num_slides=arguments.num_slides,
                                                presenter=arguments.presenter)

    # Save presentation
    if arguments.save_ppt:
        presentation_file = _save_presentation_to_pptx(arguments.output_folder, arguments.topic, presentation)

        # Open the presentation
        if arguments.open_ppt and presentation_file is not None:
            path = os.path.realpath(presentation_file)
            os.startfile(path)

    return presentation


# TEXT GENERATORS
talk_title_generator = text_generator.TemplatedTextGenerator('data/text-templates/talk_title.txt').generate
talk_subtitle_generator = text_generator.TraceryTextGenerator('data/text-templates/talk_subtitle.json').generate

inspiration_title_generator = text_generator.TemplatedTextGenerator(
    "data/text-templates/inspiration.txt").generate
history_title_generator = text_generator.TemplatedTextGenerator(
    "data/text-templates/history.txt").generate
history_person_title_generator = text_generator.TemplatedTextGenerator(
    "data/text-templates/history_person.txt").generate
history_and_history_person_title_generator = combined_generator(
    (4, history_title_generator), (6, history_person_title_generator))
about_me_title_generator = text_generator.TemplatedTextGenerator(
    "data/text-templates/about_me_title.txt").generate
historical_name_generator = text_generator.TraceryTextGenerator("./data/text-templates/name.json",
                                                                "title_name").generate
full_name_generator = text_generator.TraceryTextGenerator("./data/text-templates/name.json",
                                                          "full_name").generate

_about_me_facts_grammar = "./data/text-templates/about_me_facts.json"
book_description_generator = text_generator.TraceryTextGenerator(_about_me_facts_grammar,
                                                                 "book_description").generate
location_description_generator = text_generator.TraceryTextGenerator(_about_me_facts_grammar,
                                                                     "location_description").generate
hobby_description_generator = text_generator.TraceryTextGenerator(_about_me_facts_grammar,
                                                                  "hobby_description").generate
job_generator = text_generator.TraceryTextGenerator(_about_me_facts_grammar,
                                                    "job").generate


# QUOTES
def create_goodreads_quote_generator(max_quote_length):
    def generator(seed):
        return [quote for quote in goodreads.search_quotes(seed, 50) if len(quote) <= max_quote_length]

    return create_from_list_generator(create_seeded_generator(generator))


# INSPIROBOT
inspirobot_image_generator = inspirobot.get_random_inspirobot_image


# REDDIT
class RedditImageGenerator:
    def __init__(self, subreddit):
        self._subreddit = subreddit

        def generate(seed):
            results = reddit.search_subreddit(
                self._subreddit,
                str(seed) + " nsfw:no (url:.jpg OR url:.png OR url:.gif)")
            if bool(results):
                return [post.url for post in results]

        self._generate = create_from_external_image_list_generator(
            create_seeded_generator(generate),
            lambda url: "./downloads/reddit/" + self._subreddit + "/" + os_util.get_file_name(url)
        )

    def generate(self, presentation_context):
        return self._generate(presentation_context)

    def generate_random(self, _):
        return self.generate({"seed": ""})


def create_reddit_image_generator(*name):
    reddit_generator = RedditImageGenerator("+".join(name))
    return create_backup_generator(reddit_generator.generate, reddit_generator.generate_random)


weird_image_generator = create_reddit_image_generator("hmmm", "hmm", "wtf", "wtfstockphotos", "photoshopbattles",
                                                      "confusing_perspective", "cursedimages", "HybridAnimals")

shitpostbot_image_generator = create_from_external_image_list_generator(
    create_seeded_generator(
        create_backup_generator(
            shitpostbot.search_images,
            shitpostbot.get_random_images
        )),
    lambda url: "./downloads/shitpostbot/{}".format(os_util.get_file_name(url))
)

weird_and_shitpost_generator = combined_generator(
    (1, weird_image_generator),
    (2, shitpostbot_image_generator)
)

# GOOGLE IMAGES

generate_full_screen_google_image = create_from_list_generator(
    remove_invalid_images_from_generator(
        create_seeded_generator(
            google_images.create_full_screen_image_generator())))

generate_wide_google_image = create_from_list_generator(
    remove_invalid_images_from_generator(
        create_seeded_generator(
            google_images.create_wide_image_generator())))

generate_google_image = create_from_list_generator(
    remove_invalid_images_from_generator(
        create_seeded_generator(
            google_images.create_image_generator())))


# GIFS

def get_related_giphy(seed_word):
    giphy = safygiphy.Giphy()
    response = giphy.random(tag=seed_word)
    if bool(response):
        data = response.get('data')
        if bool(data):
            images = data.get('images')
            original = images.get('original')
            giphy_url = original.get('url')
            gif_name = os.path.basename(os.path.dirname(giphy_url))
            image_url = 'downloads/' + seed_word + '/gifs/' + gif_name + ".gif"
            os_util.download_image(giphy_url, image_url)
            return image_url


giphy_generator = create_seeded_generator(get_related_giphy)
reddit_gif_generator = create_reddit_image_generator("gifs", "gif", "gifextra", "nonononoYES")

combined_gif_generator = combined_generator((.5, giphy_generator), (.5, reddit_gif_generator))

# OLD
vintage_person_generator = create_reddit_image_generator("OldSchoolCool")
vintage_picture_generator = create_reddit_image_generator("TheWayWeWere", "100yearsago", "ColorizedHistory")

reddit_book_cover_generator = create_reddit_image_generator("BookCovers", "fakebookcovers", "coverdesign", "bookdesign")

reddit_location_image_generator = create_reddit_image_generator("evilbuildings", "itookapicture", "SkyPorn",
                                                                "EarthPorn")

# BOLD_STATEMENT

bold_statement_templated_generator = text_generator.TemplatedTextGenerator('data/text-templates/bold_statements.txt')


def generate_wikihow_bold_statement(presentation_context):
    # template_values = {
    #     "topic": seed,
    #     # TODO: Use datamuse or conceptnet or some other mechanism of finding a related location
    #     'location': 'Here'
    # }
    template_values = presentation_context
    # TODO: Sometimes "Articles Form Wikihow" is being scraped as an action, this is a bug
    related_actions = wikihow.get_related_wikihow_actions(presentation_context["seed"])
    if related_actions:
        action = random.choice(related_actions)
        template_values.update({'action': action.title(),
                                # TODO: Make a scraper that scrapes a step related to this action on wikihow.
                                'step': 'Do Whatever You Like'})

    return bold_statement_templated_generator.generate(template_values)


# DOUBLE CAPTIONS

_double_captions_generator = text_generator.TemplatedTextGenerator("./data/text-templates/double_captions.txt")


def create_double_image_captions(presentation_context):
    line = _double_captions_generator.generate(presentation_context)
    parts = line.split("|")
    return parts[0], parts[1]


# == SCHEMAS ==

# This object holds all the information about how to generate the presentation
presentation_schema = PresentationSchema(
    # Basic powerpoint generator
    slide_templates.create_new_powerpoint,
    # Topic per slide generator
    lambda topic, num_slides: slide_topic_generators.SynonymTopicGenerator(topic, num_slides),

    # Slide generators
    [
        SlideGenerator(
            slide_templates.generate_title_slide(talk_title_generator, talk_subtitle_generator),
            weight_function=create_peaked_weight([0], 100000, 0),
            name="Title slide"),
        SlideGenerator(
            slide_templates.generate_three_column_images_slide(
                about_me_title_generator,
                location_description_generator,
                reddit_location_image_generator,
                book_description_generator,
                reddit_book_cover_generator,
                hobby_description_generator,
                weird_and_shitpost_generator
            ),
            create_peaked_weight([1], 2000, 0),
            allowed_repeated_elements=0,
            name="About Me: Location-Book-WeirdHobby"),
        SlideGenerator(
            slide_templates.generate_image_slide(
                hobby_description_generator,
                weird_and_shitpost_generator
            ),
            create_peaked_weight([1, 2], 10, 0),
            allowed_repeated_elements=0,
            name="Weird Hobby"),

        SlideGenerator(
            slide_templates.generate_two_column_images_slide(
                history_and_history_person_title_generator,
                historical_name_generator,
                vintage_person_generator,
                none_generator,
                create_goodreads_quote_generator(280)
            ),
            weight_function=create_peaked_weight([1, 2], 10, 0.4),
            allowed_repeated_elements=1,
            name="Historical Figure Quote"),
        SlideGenerator(
            slide_templates.generate_two_column_images_slide(
                history_title_generator,
                none_generator,
                vintage_picture_generator,
                none_generator,
                vintage_picture_generator
            ),
            weight_function=create_peaked_weight([1, 2], 4, 0.2),
            allowed_repeated_elements=1,
            name="Two History Pictures"),
        SlideGenerator(
            slide_templates.generate_full_image_slide(
                seeded_titled_identity_generator,
                combined_gif_generator),
            name="Full Screen Giphy"),
        SlideGenerator(
            slide_templates.generate_image_slide(inspiration_title_generator, inspirobot_image_generator),
            weight_function=constant_weight(0.6),
            name="Inspirobot"),
        SlideGenerator(
            slide_templates.generate_large_quote_slide(generate_wikihow_bold_statement),
            name="Wikihow Bold Statement"),
        SlideGenerator(
            slide_templates.generate_full_image_slide(
                none_generator,
                generate_full_screen_google_image),
            name="Google Images"),
        SlideGenerator(
            slide_templates.generate_full_image_slide(
                seeded_titled_identity_generator,
                generate_wide_google_image),
            name="Google Images"),
        SlideGenerator(
            slide_templates.generate_two_column_images_slide_tuple_caption(
                seeded_titled_identity_generator,
                create_double_image_captions,
                combined_gif_generator,
                combined_gif_generator),
            name="Two Captions Gifs"),
        SlideGenerator(
            slide_templates.generate_two_column_images_slide_tuple_caption(
                seeded_titled_identity_generator,
                create_double_image_captions,
                weird_image_generator,
                weird_image_generator),
            name="Two Captions Weird Reddit"),
    ]
)

test_schema = PresentationSchema(
    # Basic powerpoint generator
    slide_templates.create_new_powerpoint,
    # Topic per slide generator
    # lambda topic, num_slides: slide_topic_generators.IdentityTopicGenerator(topic, num_slides),
    slide_topic_generators.SynonymTopicGenerator,
    # Slide generators
    [
        SlideGenerator(
            slide_templates.generate_three_column_images_slide(
                about_me_title_generator,
                location_description_generator,
                reddit_location_image_generator,
                book_description_generator,
                reddit_book_cover_generator,
                hobby_description_generator,
                combined_generator(
                    (1, weird_image_generator),
                    (2, shitpostbot_image_generator)
                )
            ),
            weight_function=constant_weight(100000),
            allowed_repeated_elements=3,
            name="About Me"),
        # Back up in case something goes wrong

        SlideGenerator(
            slide_templates.generate_image_slide(
                inspiration_title_generator,
                create_static_generator("downloads/inspirobot/01-743.jpg")),
            allowed_repeated_elements=2,
            name="Fake Inspirobot")
    ])

schemas = {
    "default": presentation_schema,
    "test": test_schema
}


def get_schema(name):
    return schemas[name]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--topic', help="Topic of presentation.",
                        default='cat', type=str)
    parser.add_argument('--num_slides', help="Number of slides to create.",
                        default=10, type=int)
    parser.add_argument('--schema', help="The presentation schema to generate the presentation with",
                        default="default", type=str)
    parser.add_argument('--presenter', help="The full name of the presenter, leave blank to randomise",
                        default=None, type=str)
    parser.add_argument('--output_folder', help="The folder to output the generated presentations",
                        default="./output/", type=str)
    parser.add_argument('--save_ppt', help="If this flag is true, the generated powerpoint will be saved",
                        default=True, type=bool)
    parser.add_argument('--open_ppt', help="If this flag is true, the generated powerpoint will automatically open",
                        default=True, type=bool)
    args = parser.parse_args()
    main(args)
