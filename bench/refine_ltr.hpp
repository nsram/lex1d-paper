// Declaration for the exploratory left-to-right Refine variant (see refine_ltr.cpp).
#pragma once
#include "detail.hpp"
#include <functional>
#include <vector>

namespace lex::detail_ltr {

lex::detail::RefineStats refine(const lex::detail::Atoms& a, std::vector<int>& b, double tolerance,
                                const std::function<void(const std::vector<int>&)>& on_move = {});

} // namespace lex::detail_ltr
