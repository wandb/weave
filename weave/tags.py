# TODO: we could generate tag class with __slots__ for efficiency


class Taggable:
    pass


TAGS_ATTR_NAME = "_weave_tags"


def with_tag(obj, name, tag):
    tags = None
    try:
        tags = getattr(obj, TAGS_ATTR_NAME)
    except AttributeError:
        tags = {}
        try:
            setattr(obj, TAGS_ATTR_NAME, tags)
        except AttributeError:
            # TODO: may want to cache for speed
            taggable_class = type(
                "Taggable-%s" % obj.__class__.__name__,
                (
                    Taggable,
                    obj.__class__,
                ),
                {},
            )
            obj = taggable_class(obj)
            setattr(obj, TAGS_ATTR_NAME, tags)

    tags[name] = tag

    # #_tags.with_tag(obj, name, tag)
    return obj


def with_tags(obj, tags):
    for name, tag in tags.items():
        obj = with_tag(obj, name, tag)
    return obj


def get_tags(obj):
    return getattr(obj, TAGS_ATTR_NAME, None)


def get_tag(obj, name):
    return getattr(obj, TAGS_ATTR_NAME, {}).get(name)
    # return _tags.get_tag(obj, name)
