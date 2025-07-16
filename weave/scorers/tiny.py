import weave
import numpy as np
from scipy.optimize import minimize

def sigmoid(z):
    return 1/(1+np.exp(-z))

def item_curve(theta, a, b):
    
    """
    Compute the item response curve for given parameters.
    
    Parameters:
    - theta: The ability parameter of the subject.
    - a: The discrimination parameter of the item.
    - b: The difficulty parameter of the item.
    
    Returns:
    - The probability of a correct response given the item parameters and subject ability.
    """
    z = np.clip(a*theta - b, -30, 30).sum(axis=1)
    return sigmoid(z)

def estimate_ability_parameters(responses_test, A, B, theta_init=None, eps=1e-10, optimizer="BFGS"):
    
    """
    Estimates the ability parameters for a new set of test responses.
    
    Parameters:
    - responses_test: A 1D array of the test subject's responses.
    - A: The discrimination parameters of the IRT model.
    - B: The difficulty parameters of the IRT model.
    - theta_init: Initial guess for the ability parameters.
    - eps: A small value to avoid division by zero and log of zero errors.
    - optimizer: The optimization method to use.
    - weights: weighting for items according to their representativeness of the whole scenario
    
    Returns: 
    - optimal_theta: The estimated ability parameters for the test subject.
    """

    D = A.shape[1]
    
    # Define the negative log likelihood function
    def neg_log_like(x):
        P = item_curve(x.reshape(1, D, 1), A, B).squeeze()
        log_likelihood = np.sum(responses_test * np.log(P + eps) + (1 - responses_test) * np.log(1 - P + eps))
        return -log_likelihood
    
    # Ensure the initial theta is a numpy array with the correct shape
    if type(theta_init) == np.ndarray:
        theta_init = theta_init.reshape(-1)
        assert theta_init.shape[0] == D
    else:
        theta_init = np.zeros(D)

    # Use the minimize function to find the ability parameters that minimize the negative log likelihood
    optimal_theta = minimize(neg_log_like, theta_init, method = optimizer).x[None,:,None] 
    
    return optimal_theta

class TinyWrapScorer(weave.Scorer):
    weight_key: str = "w_anchor"
    A_key: str = "A_anchor"
    B_key: str = "B_anchor"
    score_key: str = "score"
    child_scorer: weave.Scorer

    @weave.op
    async def score(self, *, answers: list[str], output: str, A_anchor, B_anchor, w_anchor):
        score_dict = await self.child_scorer.score(answers=answers, output=output)
        # we now need to append to our score_dict our keys
        score_dict[self.A_key] = A_anchor
        score_dict[self.B_key] = B_anchor
        score_dict[self.weight_key] = w_anchor
        return score_dict

    @weave.op
    def summarize(self, score_rows: list[dict]):
        print(score_rows)
        print(score_rows[0].keys())
        Y, A, B, W = np.array([score_row[self.score_key] for score_row in score_rows]), np.array([score_row[self.A_key] for score_row in score_rows]), np.array([score_row[self.B_key] for score_row in score_rows]), np.array([score_row[self.weight_key] for score_row in score_rows])
        
        #reshape A, B:
        # Reshape A and B to (1, 2, 100) using transpose and add batch dimension
        A = A.T[None, ...]
        B = B.T[None, ...]
        
        # weighted pred:
        pred = (Y * W).sum()
        # pirt pred:
        theta = estimate_ability_parameters(Y, A, B)
        pirt_lambda = 0.1 # TODO: get this from the dataset
        pirt_pred = pirt_lambda * (Y.mean()) + (1-pirt_lambda) * (item_curve(theta, A, B).mean()) 
        # gpirt pred:
        gpirt_lambda = 0.3 # TODO: get this from the dataset
        gpirt_pred = gpirt_lambda * pred + (1-gpirt_lambda) * pirt_pred
        return gpirt_pred
