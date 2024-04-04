import weave

# Initialize tracking to the project 'cat-project'
weave.init("intro-example")
# Save a list, giving it the name 'cat-names'
weave.publish(["felix", "jimbo", "billie"], "cat-names")


weave.init("intro-example")
cat_names = weave.ref("cat-names").get()
