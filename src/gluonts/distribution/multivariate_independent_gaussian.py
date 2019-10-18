# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

# Standard library imports
import math
from typing import Dict, Optional, Tuple

# First-party imports
from gluonts.core.component import validated
from gluonts.model.common import Tensor

# Relative imports
from gluonts.support.erf import erf
from .distribution import Distribution, _sample_multiple, getF, softplus
from .distribution_output import DistributionOutput


class MultivariateIndependentGaussian(Distribution):
    r"""
    Gaussian distribution.

    Parameters
    ----------
    mu
        Tensor containing the means, of shape `(*batch_shape, *event_shape)`.
    sigma
        Tensor containing the standard deviations, of shape
        `(*batch_shape, *event_shape)`.
    dim
        Dimension, only required to get the diagonal covariance matrix
    """

    is_reparameterizable = True

    def __init__(
        self, mu: Tensor, sigma: Tensor, dim: Optional[int] = None
    ) -> None:
        self.mu = mu
        self.sigma = sigma
        self.dim = dim

    @property
    def batch_shape(self) -> Tuple:
        return self.mu.shape

    @property
    def event_shape(self) -> Tuple:
        return self.mu.shape[:-1]

    @property
    def event_dim(self) -> int:
        return 1

    def log_prob(self, x: Tensor) -> Tensor:
        # TODO
        F = getF(x)
        mu, sigma = self.mu, self.sigma
        return -1.0 * (
            F.log(sigma)
            + 0.5 * math.log(2 * math.pi)
            + 0.5 * F.square((x - mu) / sigma)
        ).sum(axis=-1)

    @property
    def mean(self) -> Tensor:
        return self.mu

    @property
    def stddev(self) -> Tensor:
        F = getF(self.sigma)
        return self.sigma * F.eye(self.dim)

    def cdf(self, x):
        F = self.F
        u = self.F.broadcast_div(
            self.F.broadcast_minus(x, self.mu), self.sigma * math.sqrt(2.0)
        )
        return (erf(F, u) + 1.0) / 2.0

    def sample(self, num_samples: Optional[int] = None) -> Tensor:
        return _sample_multiple(
            getF(self.mu).sample_normal,
            mu=self.mu,
            sigma=self.sigma,
            num_samples=num_samples,
        )

    def sample_rep(self, num_samples: Optional[int] = None) -> Tensor:
        def s(mu: Tensor, sigma: Tensor) -> Tensor:
            raw_samples = getF(self.mu).sample_normal(
                mu=mu.zeros_like(), sigma=sigma.ones_like()
            )
            return sigma * raw_samples + mu

        return _sample_multiple(
            s, mu=self.mu, sigma=self.sigma, num_samples=num_samples
        )


class MultivariateIndependentGaussianOutput(DistributionOutput):
    @validated()
    def __init__(self, dim: int) -> None:
        self.args_dim = {"mu": dim, "sigma": dim}
        self.distr_cls = MultivariateIndependentGaussian
        self.dim = dim

    @classmethod
    def domain_map(cls, F, mu, sigma):
        r"""
        Maps raw tensors to valid arguments for constructing a Gaussian
        distribution.

        Parameters
        ----------
        F
        mu
            Tensor of shape `(*batch_shape, dim)`
        sigma
            Tensor of shape `(*batch_shape, dim)`

        Returns
        -------
        Tuple[Tensor, Tensor]
            Two squeezed tensors, of shape `(*batch_shape)`: the first has the
            same entries as `mu` and the second has entries mapped to the
            positive orthant.
        """
        return mu, softplus(F, sigma)

    @property
    def event_shape(self) -> Tuple:
        return (self.dim,)
